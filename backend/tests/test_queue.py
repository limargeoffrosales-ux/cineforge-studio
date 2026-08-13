"""Queue tests — DB-backed job lifecycle: recovery, retry budget, resume, and
the dispatcher picking up interrupted work after a simulated restart."""
import os
import sys
import time
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_queue.db")
os.environ.setdefault("PIPELINE_STAGE_SECONDS", "0.03")
os.environ.setdefault("PIPELINE_FAST", "1")
os.environ.setdefault("CINEFORGE_STILLS", "off")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import timedelta  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.db import Base, SessionLocal, engine, utcnow  # noqa: E402
from app.models import PipelineRun, Project, RenderJob, VideoClip  # noqa: E402

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)


def _project(owner_id="queuetest") -> Project:
    p = Project(id=uuid.uuid4().hex, owner_id=owner_id, title="Q", topic="Rice Terraces",
                category="youtube", tone="epic", language="en", target_duration=30)
    shot = {"id": "shot-1", "shot_type": "Wide", "framing": "medium", "lens": "35mm", "camera_type": "Gimbal",
            "movement": "Orbit", "background": "Banaue Rice Terraces — Golden Hour", "time_of_day": "golden hour",
            "weather": "clear", "lighting": "Golden hour rim", "mood": "epic", "duration": 3.0}
    shot2 = {**shot, "id": "shot-2", "shot_type": "Close-up", "background": "Palawan Cliffs — Sunset", "duration": 3.0}
    p.outputs = {"video_generation": {"scenes": [
        {"id": "scene-1", "title": "S1", "duration": 3, "clips": [{"shot": shot, "routing": {"chosen": "kling-3.0", "reasons": ["t"]}}]},
        {"id": "scene-2", "title": "S2", "duration": 3, "clips": [{"shot": shot2, "routing": {"chosen": "kling-3.0", "reasons": ["t"]}}]},
    ]}}
    return p


def _job(project: Project, **kw) -> RenderJob:
    j = RenderJob(id=uuid.uuid4().hex, owner_id=project.owner_id, project_id=project.id,
                  scene_label="Full timeline", model="auto", resolution="480p", fps=18,
                  priority=5, params={}, status="queued")
    for k, v in kw.items():
        setattr(j, k, v)
    return j


def _commit(*objs):
    db = SessionLocal()
    try:
        for o in objs:
            db.add(o)
        db.commit()
        return db
    finally:
        db.close()


def test_recover_requeues_stale_and_budget_fails():
    db = SessionLocal()
    p = _project()
    stale = _job(p, worker_id="dead-worker", attempts=1, max_attempts=5, last_heartbeat=utcnow() - timedelta(hours=1))
    exhausted = _job(p, worker_id="dead-worker", attempts=2, max_attempts=2, last_heartbeat=utcnow() - timedelta(hours=1))
    fresh = _job(p)  # queued with no worker — untouched by recovery
    db.add_all([p, stale, exhausted, fresh])
    db.commit()

    from app.services import queue

    report = queue.recover()
    db.expire_all()

    stale = db.get(RenderJob, stale.id)
    exhausted = db.get(RenderJob, exhausted.id)
    fresh = db.get(RenderJob, fresh.id)
    assert stale.status == "queued" and stale.worker_id is None and stale.attempts == 2
    assert exhausted.status == "failed" and "attempts" in exhausted.error
    assert fresh.status == "queued" and fresh.attempts == 0
    assert report["render_requeued"] == 1 and report["failed"] == 1
    db.close()


def test_recover_resets_inflight_clips_but_keeps_completed():
    db = SessionLocal()
    p = _project()
    j = _job(p, worker_id="dead-worker", attempts=1, max_attempts=5, last_heartbeat=utcnow() - timedelta(hours=1))
    db.add_all([p, j])
    db.commit()
    done = VideoClip(job_id=j.id, project_id=p.id, scene_id="scene-1", clip_ref="c1", provider="kling-3.0",
                     status="completed", file_path="media/final/x.mp4", created_at=utcnow())
    inflight = VideoClip(job_id=j.id, project_id=p.id, scene_id="scene-2", clip_ref="c2", provider="kling-3.0",
                         status="rendering", created_at=utcnow())
    db.add_all([done, inflight])
    db.commit()
    db.close()

    from app.services import queue

    queue.recover()
    db = SessionLocal()
    clips = db.scalars(select(VideoClip).where(VideoClip.job_id == j.id)).all()
    by_ref = {c.clip_ref: c for c in clips}
    assert by_ref["c1"].status == "completed"  # untouched
    assert by_ref["c2"].status == "queued"  # requeued for the resumed worker
    db.close()


def test_render_worker_resumes_without_rerendering_completed_clips():
    from app.services.render import render_engine

    db = SessionLocal()
    p = _project()
    j = _job(p)
    db.add_all([p, j])
    db.commit()
    db.close()

    render_engine._worker(j.id)  # first pass — both clips render

    db = SessionLocal()
    j = db.get(RenderJob, j.id)
    assert j.status == "completed"
    clips = db.scalars(select(VideoClip).where(VideoClip.job_id == j.id).order_by(VideoClip.clip_ref)).all()
    assert len(clips) == 2 and all(c.status == "completed" and c.file_path for c in clips)
    first_done_at = clips[0].completed_at
    first_file = clips[0].file_path
    # simulate an interrupted job: requeue it, one clip back to queued
    j.status = "queued"
    j.worker_id = None
    clips[1].status = "queued"
    db.commit()
    db.close()

    render_engine._worker(j.id)  # resumed pass

    db = SessionLocal()
    clips = db.scalars(select(VideoClip).where(VideoClip.job_id == j.id).order_by(VideoClip.clip_ref)).all()
    print("CLIPS", [(c.clip_ref, c.status, c.error) for c in clips], flush=True)
    assert all(c.status == "completed" for c in clips), [(c.clip_ref, c.status, c.error) for c in clips]
    assert clips[0].completed_at == first_done_at, "completed clip must not be re-rendered"
    assert clips[0].file_path == first_file
    db.close()


def test_dispatcher_completes_interrupted_job_after_recovery():
    """Simulates a restart: a job left mid-render by a dead worker is picked up
    by a fresh dispatcher, requeued, resumed (completed clip skipped)."""
    from app.services import queue
    from app.services.render import render_engine

    db = SessionLocal()
    p = _project()
    j = _job(p)
    db.add_all([p, j])
    db.commit()
    db.close()

    render_engine._worker(j.id)  # fully render once
    db = SessionLocal()
    clips = db.scalars(select(VideoClip).where(VideoClip.job_id == j.id).order_by(VideoClip.clip_ref)).all()
    first_done_at = clips[0].completed_at
    first_file = clips[0].file_path
    # "crash" mid-job: foreign worker, clip 2 back to rendering, stale heartbeat
    j = db.get(RenderJob, j.id)  # reattach to this session before mutating
    j.worker_id = "dead-worker"
    j.status = "rendering"
    j.attempts = 1
    j.last_heartbeat = utcnow() - timedelta(hours=1)
    clips[1].status = "rendering"
    db.commit()
    db.close()

    queue.start_dispatcher()
    try:
        deadline = time.time() + 60
        done = False
        while time.time() < deadline:
            db = SessionLocal()
            j = db.get(RenderJob, j.id)
            if j and j.status in ("completed", "failed"):
                done = j.status == "completed"
                db.close()
                break
            db.close()
            time.sleep(0.5)
    finally:
        queue.stop_dispatcher()
    assert done, "job never completed"

    db = SessionLocal()
    j = db.get(RenderJob, j.id)
    clips = db.scalars(select(VideoClip).where(VideoClip.job_id == j.id).order_by(VideoClip.clip_ref)).all()
    assert all(c.status == "completed" for c in clips), [(c.clip_ref, c.status, c.error) for c in clips]
    assert clips[0].completed_at == first_done_at, "recovered job must skip already-completed clips"
    assert clips[0].file_path == first_file
    assert j.attempts >= 2  # recovery counted the interruption
    db.close()


def test_pipeline_run_survives_recovery():
    """A pipeline run abandoned mid-flight is requeued (not failed) on boot."""
    db = SessionLocal()
    p = _project()
    run = PipelineRun(project_id=p.id, status="running", worker_id="dead-worker", attempts=1, max_attempts=3,
                      last_heartbeat=utcnow() - timedelta(hours=1), start_stage="")
    db.add_all([p, run])
    db.commit()
    db.close()

    from app.services import queue

    queue.recover()
    db = SessionLocal()
    run = db.get(PipelineRun, run.id)
    assert run.status == "queued" and run.worker_id is None and run.attempts == 2
    db.close()