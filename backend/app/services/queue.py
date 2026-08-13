"""DB-backed job queue + dispatcher.

Renders and pipeline runs live in `render_jobs` / `pipeline_runs` rows instead
of bare threads, so work survives a server restart:

  * `render_engine.start()` and `engine.start()` only *enqueue* (set status to
    queued) — no thread is spawned.
  * A single dispatcher thread (started in the FastAPI lifespan) claims queued
    work, stamps the row with this process's `worker_id`, and runs the real
    worker inline while updating `last_heartbeat` between steps.
  * `recover()` runs at boot: any row still queued/running whose worker died
    (stale heartbeat / foreign worker_id) is requeued with an attempt budget
    (default 3). A requeued render job *resumes* by skipping clips that were
    already completed, and its in-flight clips are reset back to queued.
    Jobs past their budget fail honestly with a persisted error.

Single-process by design (one dispatcher owns the tables); `worker_id` makes
multi-process/multi-node future-proofing possible without a scheduler.
"""
from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select

from ..db import SessionLocal, utcnow
from ..models import PipelineRun, RenderJob, VideoClip

log = logging.getLogger("cineforge.queue")

WORKER_ID = uuid.uuid4().hex[:12]

MAX_ATTEMPTS = int(os.getenv("JOB_MAX_ATTEMPTS", "3"))
STALE_AFTER_S = int(os.getenv("JOB_HEARTBEAT_STALE_S", "120"))
_POLL_S = float(os.getenv("JOB_POLL_SECONDS", "1.0"))
RENDER_CONCURRENCY = max(1, int(os.getenv("RENDER_CONCURRENCY", "2")))
PIPELINE_CONCURRENCY = max(1, int(os.getenv("PIPELINE_CONCURRENCY", "1")))

_claim_lock = threading.Lock()
_stop = threading.Event()
_thread: threading.Thread | None = None
_pipeline_threads: list[threading.Thread] = []


# ------------------------------------------------------------------ claiming
def claim_render_job() -> RenderJob | None:
    """Atomically take the next queued render job for this process."""
    with _claim_lock:
        db = SessionLocal()
        try:
            job = db.scalars(
                select(RenderJob)
                .where(RenderJob.status == "queued")
                .order_by(RenderJob.priority.desc(), RenderJob.created_at)
                .limit(1)
            ).first()
            if not job:
                return None
            job.status = "rendering"
            job.worker_id = WORKER_ID
            job.attempts = (job.attempts or 0) + 1
            job.last_heartbeat = utcnow()
            job.started_at = job.started_at or utcnow()
            db.commit()
            return job
        finally:
            db.close()


def claim_pipeline_run() -> PipelineRun | None:
    """Atomically take the next queued pipeline run for this process."""
    with _claim_lock:
        db = SessionLocal()
        try:
            run = db.scalars(
                select(PipelineRun)
                .where(PipelineRun.status == "queued")
                .order_by(PipelineRun.started_at)
                .limit(1)
            ).first()
            if not run:
                return None
            run.status = "running"
            run.worker_id = WORKER_ID
            run.attempts = (run.attempts or 0) + 1
            run.last_heartbeat = utcnow()
            run.started_at = run.started_at or utcnow()
            db.commit()
            return run
        finally:
            db.close()


def touch(kind: str, entity_id: str) -> None:
    """Refresh a claim's heartbeat so the watchdog won't requeue it."""
    model = RenderJob if kind == "render" else PipelineRun
    db = SessionLocal()
    try:
        row = db.get(model, entity_id)
        if row and row.worker_id == WORKER_ID:
            row.last_heartbeat = utcnow()
            db.commit()
    finally:
        db.close()


# --------------------------------------------------------------- recovery
def _reset_inflight_clips(job: RenderJob) -> None:
    """Return clips interrupted mid-render to the queue; completed clips are
    kept so the resumed worker can skip them. No-ops if the job is already
    claimed by a live worker (recover() can race the claim across threads)."""
    db = SessionLocal()
    try:
        current = db.get(RenderJob, job.id)
        if not current or current.worker_id == WORKER_ID:
            return
        clips = db.scalars(
            select(VideoClip).where(VideoClip.job_id == job.id, VideoClip.status.in_(("rendering", "failed")))
        ).all()
        for clip in clips:
            clip.status = "queued"
            clip.error = ""
        db.commit()
    finally:
        db.close()


def recover() -> dict:
    """Boot-time recovery of interrupted work. Returns a small report."""
    report = {"render_requeued": 0, "pipeline_requeued": 0, "failed": 0, "assemblies_retriggered": 0}
    db = SessionLocal()
    try:
        # render jobs
        jobs = db.scalars(
            select(RenderJob).where(RenderJob.status.in_(("queued", "rendering")))
        ).all()
        for job in jobs:
            if job.status == "queued" and not job.worker_id:
                continue  # fresh enqueued job — the dispatcher will claim it
            if job.worker_id == WORKER_ID:
                continue  # live in this process
            job.attempts = (job.attempts or 0) + 1
            if job.attempts > (job.max_attempts or MAX_ATTEMPTS):
                job.status = "failed"
                job.error = f"interrupted after {job.attempts} attempts (worker died)"
                job.finished_at = utcnow()
                report["failed"] += 1
            else:
                job.status = "queued"
                job.worker_id = None
                job.last_heartbeat = None
                _reset_inflight_clips(job)
                report["render_requeued"] += 1

        # pipeline runs
        runs = db.scalars(
            select(PipelineRun).where(PipelineRun.status.in_(("queued", "running")))
        ).all()
        for run in runs:
            if run.status == "queued" and not run.worker_id:
                continue
            if run.worker_id == WORKER_ID:
                continue
            run.attempts = (run.attempts or 0) + 1
            if run.attempts > (run.max_attempts or MAX_ATTEMPTS):
                run.status = "failed"
                run.error = f"interrupted after {run.attempts} attempts (worker died)"
                run.finished_at = utcnow()
                report["failed"] += 1
            else:
                run.status = "queued"
                run.worker_id = None
                run.last_heartbeat = None
                report["pipeline_requeued"] += 1

        # completed render jobs whose assembly was cut short — re-stitch.
        done = db.scalars(
            select(RenderJob).where(RenderJob.status == "completed", RenderJob.final_url == "")
        ).all()
        for job in done:
            clips = db.scalars(
                select(VideoClip).where(VideoClip.job_id == job.id)
            ).all()
            files = [c for c in clips if c.status == "completed" and c.file_path and Path(c.file_path).exists()]
            if clips and len(files) == len(clips):
                from .render import render_engine  # noqa: PLC0415

                render_engine.assemble(job.id)
                report["assemblies_retriggered"] += 1
        db.commit()
        if report["render_requeued"] or report["pipeline_requeued"] or report["failed"] or report["assemblies_retriggered"]:
            log.info("recovery %s (worker=%s)", report, WORKER_ID)
    finally:
        db.close()
    return report


# --------------------------------------------------------------- dispatcher
def _render_loop() -> None:
    """Claim and render jobs sequentially (render concurrency = 1)."""
    recover()
    while not _stop.is_set():
        job = None
        try:
            job = claim_render_job()
        except Exception:  # noqa: BLE001
            log.exception("claim render failed")
        if job:
            from .render import render_engine  # noqa: PLC0415

            try:
                render_engine._worker(job.id)
            except Exception:  # noqa: BLE001
                log.exception("dispatcher render worker crashed")
        else:
            _stop.wait(_POLL_S)


def _pipeline_loop() -> None:
    """Claim and run pipeline runs sequentially (pipeline concurrency = 1)."""
    recover()
    while not _stop.is_set():
        run = None
        try:
            run = claim_pipeline_run()
        except Exception:  # noqa: BLE001
            log.exception("claim pipeline failed")
        if run:
            from .pipeline import engine  # noqa: PLC0415

            try:
                engine._worker(run.id)
            except Exception:  # noqa: BLE001
                log.exception("dispatcher pipeline worker crashed")
        else:
            _stop.wait(_POLL_S)


def start_dispatcher() -> None:
    """Start the dispatcher worker threads (called from the app lifespan)."""
    global _thread, _pipeline_threads
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_render_loop, name="cineforge-render-0", daemon=True)
    _thread.start()
    for i in range(1, RENDER_CONCURRENCY):
        threading.Thread(target=_render_loop, name=f"cineforge-render-{i}", daemon=True).start()
    _pipeline_threads = []
    for i in range(PIPELINE_CONCURRENCY):
        t = threading.Thread(target=_pipeline_loop, name=f"cineforge-pipeline-{i}", daemon=True)
        t.start()
        _pipeline_threads.append(t)
    log.info("dispatcher started (worker=%s, render=%d, pipeline=%d, poll=%ss)",
             WORKER_ID, RENDER_CONCURRENCY, PIPELINE_CONCURRENCY, _POLL_S)


def stop_dispatcher() -> None:
    _stop.set()
