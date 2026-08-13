"""CineForge AI Pipeline Engine.

Orchestrates the 18-stage production pipeline as a state machine, runs it in
a background worker thread, checkpoints every stage output onto the project
(so a crash resumes, never restarts), and broadcasts live progress over
WebSockets. Stage order mirrors the studio workflow:

  idea → research → script → storyboard → scene_planning → character_design
  → environment_design → shot_planning → video_generation → voice_generation
  → sound_design → music → editing → motion_graphics → subtitles → thumbnail
  → seo → publishing

Each stage is a small function (real LLM path + procedural fallback), which
makes individual stages swappable — swap `video_generation` for a Veo/Runway/
Kling provider by replacing one function and setting VIDEO_PROVIDER.
"""
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Callable

from sqlalchemy import select

from ..db import SessionLocal, utcnow
from ..models import AnalyticsSnapshot, PipelineRun, Project, PublishEntry, RenderJob
from ..config import settings
from . import generators
from .llm import llm_json

log = logging.getLogger("cineforge.pipeline")


# ------------------------------------------------------------------ stages
STAGES: list[dict] = [
    {"id": "idea", "name": "Idea", "phase": "Pre-Production", "desc": "Refine the creative brief, angle and audience."},
    {"id": "research", "name": "Research", "phase": "Pre-Production", "desc": "Gather findings, timeline, outline, hooks and references."},
    {"id": "script", "name": "Script", "phase": "Pre-Production", "desc": "Write the full narration script with scenes and direction."},
    {"id": "storyboard", "name": "Storyboard", "phase": "Pre-Production", "desc": "Turn the script into visual panels with camera & lighting."},
    {"id": "scene_planning", "name": "Scene Planning", "phase": "Pre-Production", "desc": "Production plan per scene: setting, props, environment."},
    {"id": "character_design", "name": "Character Design", "phase": "Design", "desc": "Consistent digital actors with voice, look and expressions."},
    {"id": "environment_design", "name": "Environment Design", "phase": "Design", "desc": "Reusable cinematic locations with lighting & weather."},
    {"id": "shot_planning", "name": "Shot Planning", "phase": "Design", "desc": "Shot list: camera, lens, movement, framing, time of day."},
    {"id": "video_generation", "name": "Video Generation", "phase": "Production", "desc": "Render scenes through the configured video provider."},
    {"id": "voice_generation", "name": "Voice Generation", "phase": "Production", "desc": "Synthesize narration with emotion and lip-sync data."},
    {"id": "sound_design", "name": "Sound Design", "phase": "Production", "desc": "SFX, ambience, foley and crowd layers."},
    {"id": "music", "name": "Music", "phase": "Production", "desc": "Per-scene scoring with mood, BPM and mastering targets."},
    {"id": "editing", "name": "Editing", "phase": "Post-Production", "desc": "Assembly, smart cuts, b-roll, color grade, speed ramps."},
    {"id": "motion_graphics", "name": "Motion Graphics", "phase": "Post-Production", "desc": "Titles, lower thirds, charts, callouts and infographics."},
    {"id": "subtitles", "name": "Subtitles", "phase": "Post-Production", "desc": "Captions with word highlighting, styles and exports."},
    {"id": "thumbnail", "name": "Thumbnail", "phase": "Post-Production", "desc": "CTR-optimized thumbnail concepts."},
    {"id": "seo", "name": "SEO", "phase": "Distribution", "desc": "Titles, description, tags, hashtags, chapters, keywords."},
    {"id": "publishing", "name": "Publishing", "phase": "Distribution", "desc": "Push to platforms via their official APIs."},
]
STAGE_IDS = [s["id"] for s in STAGES]
STAGE_INDEX = {s["id"]: i for i, s in enumerate(STAGES)}
PHASES = ["Pre-Production", "Design", "Production", "Post-Production", "Distribution"]


def initial_stages() -> dict:
    return {
        s["id"]: {
            "status": "pending",  # pending|running|completed|skipped
            "progress": 0,
            "started_at": None,
            "completed_at": None,
            "notes": "",
        }
        for s in STAGES
    }


# ------------------------------------------------------------ stage logic
def _stage_idea(p: Project, ctx: dict) -> dict:
    r = generators.rng(f"idea:{p.id}")
    angle = r.choice([a.format(topic=p.topic) for a in generators.ANGLES])
    return {
        "brief": {
            "topic": p.topic,
            "category": p.category,
            "language": p.language,
            "tone": p.tone,
            "target_duration_s": p.target_duration,
        },
        "selected_angle": angle,
        "audience": generators.AUDIENCE,
        "success_metric": r.choice(["retention > 60%", "CTR > 6%", "shares > 5%", "completion rate > 45%"]),
    }


def _stage_research(p: Project, ctx: dict) -> dict:
    llm = None
    if settings.llm_enabled:
        llm = llm_json(
            "You are CineForge's research director. Return JSON: {summary, findings:[{title,summary,confidence}], timeline:[{year,event}], outline:[{section,purpose,duration_pct}], angles:[str], hooks:[str]}",
            f"Research topic: {p.topic} (language {p.language}). Produce a tight, factual briefing suitable for a {p.category} video.",
        )
    return llm or generators.generate_research(p.topic, p.language, p.id)


def _stage_script(p: Project, ctx: dict) -> dict:
    research = p.outputs.get("research") or ctx.get("research")
    llm = None
    if settings.llm_enabled:
        llm = llm_json(
            "You are a world-class video scriptwriter. Return JSON: {title, hook, scenes:[{id,title,duration,tone,setting,dialogue:[{speaker,line,emotion}],direction,transition,audio_cue}]}",
            f"Topic: {p.topic}. Tone: {p.tone}. Category: {p.category}. Target duration: {p.target_duration}s. Language: {p.language}.",
        )
    script = llm or generators.generate_script(p.topic, p.language, p.tone, p.category, p.target_duration, p.id, research)
    ctx["script"] = script
    return script


def _stage_storyboard(p: Project, ctx: dict) -> dict:
    script = p.outputs.get("script") or ctx["script"]
    panels = generators.generate_storyboard(script, p.id)
    return {"panels": panels, "style_notes": "Rule of thirds default; hero shots reserved for the payoff scene."}


def _stage_scene_planning(p: Project, ctx: dict) -> dict:
    script = p.outputs.get("script") or ctx["script"]
    return {
        "scenes": [
            {
                "id": s["id"],
                "title": s["title"],
                "duration": s["duration"],
                "setting": s["setting"],
                "props": generators.pick(generators.rng(f"props:{s['id']}"), ["none", "coffee cup", "map", "notebook", "camera rig", "lantern"], 1),
                "environment_family": generators.pick(generators.rng(f"envf:{s['id']}"), ["studio", "philippine_landmark", "urban", "nature", "interior"], 1)[0],
                "weather_default": "clear",
                "time_of_day": ["dawn", "golden hour", "midday", "night"][int(s["id"].split("-")[1]) % 4],
                "vfx_wishlist": ["sky replacement", "particles", "cleanup"][int(s["id"].split("-")[1]) % 3],
            }
            for s in script["scenes"]
        ]
    }


def _stage_characters(p: Project, ctx: dict) -> dict:
    script = p.outputs.get("script") or ctx["script"]
    chars = generators.generate_characters(script, p.id)
    p.characters = chars
    return {"characters": chars, "consistency": {"mode": "locked appearance", "face_ref": None, "notes": "Enable face reference upload in Character Studio."}}


def _stage_environments(p: Project, ctx: dict) -> dict:
    script = p.outputs.get("script") or ctx["script"]
    envs = generators.generate_environments(script, p.id)
    p.environments = envs
    return {"environments": envs}


def _stage_shots(p: Project, ctx: dict) -> dict:
    script = p.outputs.get("script") or ctx["script"]
    envs = p.environments or ctx.get("environments", [])
    shots = generators.generate_shots(script, envs, p.id)
    return {"shots": shots, "coverage": "2 shots per scene minimum; hero shot on payoff scene."}


def _stage_video(p: Project, ctx: dict) -> dict:
    script = p.outputs.get("script") or ctx["script"]
    shots = p.outputs.get("shot_planning", {}).get("shots", [])
    provider = settings.VIDEO_PROVIDER
    project_dict = {
        "id": p.id, "topic": p.topic, "tone": p.tone, "category": p.category,
        "language": p.language, "target_duration": p.target_duration,
        "characters": p.characters or [], "environments": p.environments or [],
    }
    scenes_out = []
    for s in script["scenes"]:
        scene_shots = [sh for sh in shots if sh["scene_id"] == s["id"]]
        if not scene_shots:  # fallback: one generic clip per scene
            scene_shots = [{"id": f"{s['id']}-shot-1", "shot_type": "Wide", "framing": "medium", "lens": "35mm",
                            "camera_type": "Gimbal", "movement": "Push In", "background": s["setting"],
                            "time_of_day": "golden hour", "weather": "clear", "duration": s["duration"] / 2}]
        clips_out = []
        for i, sh in enumerate(scene_shots):
            from .video.router import route_scene
            from .video.prompts import build_spec, aspect_for

            if provider in ("auto", "mock"):
                decision = route_scene(sh, s, project_dict)
            else:
                decision = {"chosen": provider, "score": 0, "quality": 0, "alternatives": [], "reasons": ["user override"], "features": {}}
            w, h = (1920, 1080) if aspect_for(p.category) == "16:9" else (1080, 1920)
            spec = build_spec(sh, s, project_dict, decision, i + 1, fps=30)
            clips_out.append(
                {
                    "clip_id": spec["clip_id"],
                    "shot": sh,
                    "prompt": spec["prompt"],
                    "negative_prompt": spec["negative_prompt"],
                    "provider": decision["chosen"],
                    "routing": decision,
                    "duration_s": round(sh.get("duration", s["duration"] / 2), 1),
                    "width": w, "height": h, "fps": 30, "seed": spec["seed"],
                    "aspect_ratio": spec["aspect_ratio"],
                    "status": "render_pending",
                }
            )
        scenes_out.append({"scene_id": s["id"], "title": s["title"], "clips": clips_out})
    from .video.router import ensemble_uplift

    return {
        "provider": provider,
        "scenes": scenes_out,
        "consistency": {"character_locked": True, "temporal": "last-frame chaining", "physics": "enabled"},
        "resolutions": ["1080p", "2K", "4K"],
        "fps": 30,
        "ensemble": ensemble_uplift(project_dict),
        "provider_note": "Per-scene routing across Veo 3.1 / Runway Gen-4.5 / Kling 3.0 / Seedance 2.0 via the provider adapter layer.",
    }


def _stage_voice(p: Project, ctx: dict) -> dict:
    script = p.outputs.get("script") or ctx["script"]
    chars = p.characters or ctx.get("characters", [])
    return generators.generate_voice_plan(script, chars)


def _stage_sound(p: Project, ctx: dict) -> dict:
    script = p.outputs.get("script") or ctx["script"]
    return generators.generate_sound_design(script, p.id)


def _stage_music(p: Project, ctx: dict) -> dict:
    script = p.outputs.get("script") or ctx["script"]
    return generators.generate_music_plan(script, p.id)


def _stage_editing(p: Project, ctx: dict) -> dict:
    script = p.outputs.get("script") or ctx["script"]
    return generators.generate_edit_plan(script, p.id)


def _stage_motion(p: Project, ctx: dict) -> dict:
    script = p.outputs.get("script") or ctx["script"]
    return generators.generate_motion_graphics(script, p.id)


def _stage_subtitles(p: Project, ctx: dict) -> dict:
    voice = p.outputs.get("voice_generation") or ctx.get("voice", {})
    script = p.outputs.get("script") or ctx["script"]
    if not voice:
        voice = generators.generate_voice_plan(script, p.characters or [])
    return generators.generate_subtitles(voice, p.language)


def _stage_thumbnail(p: Project, ctx: dict) -> dict:
    script = p.outputs.get("script") or ctx["script"]
    thumbs = generators.generate_thumbnails(p.topic, script.get("title", p.title), p.id)
    return {"concepts": thumbs, "branding": {"watermark": "none", "intro": "none", "outro": "none"}}


def _stage_seo(p: Project, ctx: dict) -> dict:
    script = p.outputs.get("script") or ctx["script"]
    llm = None
    if settings.llm_enabled:
        llm = llm_json(
            "You are CineForge's SEO director. Return JSON: {titles:[str], description:str, tags:[str], hashtags:[str], keywords:[str], chapters:[{start,label}]}",
            f"Video title: {script.get('title')}. Topic: {p.topic}. Platform-optimized metadata.",
        )
    return llm or generators.generate_seo(p.topic, script.get("title", p.title), script, p.id)


def _stage_publish(p: Project, ctx: dict) -> dict:
    seo = p.outputs.get("seo") or {}
    return {
        "platforms": generators.PUBLISH_PLATFORMS,
        "suggested": {"primary": "youtube", "secondary": ["tiktok", "facebook"]},
        "metadata": seo,
        "status": "ready_for_approval",
    }


STAGE_FNS: dict[str, Callable[[Project, dict], dict]] = {
    "idea": _stage_idea,
    "research": _stage_research,
    "script": _stage_script,
    "storyboard": _stage_storyboard,
    "scene_planning": _stage_scene_planning,
    "character_design": _stage_characters,
    "environment_design": _stage_environments,
    "shot_planning": _stage_shots,
    "video_generation": _stage_video,
    "voice_generation": _stage_voice,
    "sound_design": _stage_sound,
    "music": _stage_music,
    "editing": _stage_editing,
    "motion_graphics": _stage_motion,
    "subtitles": _stage_subtitles,
    "thumbnail": _stage_thumbnail,
    "seo": _stage_seo,
    "publishing": _stage_publish,
}


# ---------------------------------------------------------------- engine
class PipelineEngine:
    """Runs pipeline runs for a project through the DB-backed queue,
    checkpointing outputs and broadcasting progress. One run at a time per
    project; runs survive restarts (requeued with an attempt budget)."""

    def is_running(self, project_id: str) -> bool:
        db = SessionLocal()
        try:
            rows = db.scalars(
                select(PipelineRun).where(
                    PipelineRun.project_id == project_id,
                    PipelineRun.status.in_(("queued", "running")),
                )
            ).all()
            return bool(rows)
        finally:
            db.close()

    def start(self, project_id: str, start_stage: str | None = None) -> dict:
        """Enqueue a pipeline run for the dispatcher. No thread is spawned."""
        db = SessionLocal()
        try:
            if self.is_running(project_id):
                return {"started": False, "reason": "A pipeline run is already in progress."}
            run = PipelineRun(project_id=project_id, status="queued", start_stage=start_stage or "")
            db.add(run)
            db.commit()
            return {"started": True, "run_id": run.id, "note": f"Pipeline queued from stage '{start_stage or 'idea'}'."}
        finally:
            db.close()

    # ------------------------------------------------------------- worker
    def _worker(self, run_id: str) -> None:
        from .queue import WORKER_ID  # noqa: PLC0415

        db = SessionLocal()
        run = None
        project_id = ""
        try:
            run = db.get(PipelineRun, run_id)
            if not run:
                return
            project_id = run.project_id
            start_stage = run.start_stage or None
            run.status = "running"
            run.worker_id = WORKER_ID
            run.last_heartbeat = utcnow()
            db.commit()

            p = db.get(Project, project_id)
            if not p:
                run.status = "failed"
                run.error = "project missing"
                run.finished_at = utcnow()
                db.commit()
                return
            if not p.stages:
                p.stages = initial_stages()

            start_idx = STAGE_INDEX.get(start_stage, 0) if start_stage else 0
            if start_idx == 0:
                p.outputs = {}  # full re-run regenerates everything
            # stages before the resume point keep their prior state (completed
            # if they were run before); stages from the resume point reset.
            for stage in STAGES[start_idx:]:
                p.stages[stage["id"]]["status"] = "pending"
                p.stages[stage["id"]]["progress"] = 0
                p.outputs.pop(stage["id"], None)

            p.status = "in_production" if start_idx < STAGE_INDEX["video_generation"] else "post_production"
            p.current_stage = STAGES[start_idx]["id"]
            db.commit()

            ctx: dict[str, Any] = {}

            def ensure_deps(sid: str) -> None:
                """Synthesize any missing upstream outputs so a stage can run
                standalone (e.g. resume from 'seo' without prior outputs)."""
                idx = STAGE_INDEX[sid]
                for dep in STAGES[:idx]:
                    did = dep["id"]
                    if did not in p.outputs:
                        try:
                            p.outputs[did] = STAGE_FNS[did](p, ctx)
                            dstate = p.stages[did]
                            dstate["status"] = "completed"
                            dstate["progress"] = 100
                            dstate["notes"] = "synthesized (resumed from later stage)"
                        except Exception as exc:  # noqa: BLE001
                            log.warning("dependency synthesis failed for %s: %s", did, exc)

            for stage in STAGES[start_idx:]:
                sid = stage["id"]
                ensure_deps(sid)
                state = p.stages[sid]
                state["status"] = "running"
                state["started_at"] = utcnow().isoformat()
                p.current_stage = sid
                db.commit()
                self._broadcast(project_id, "stage_update", {"project_id": project_id, "stage_id": sid, "status": "running", "project_progress": self._progress(p)})

                t0 = time.time()
                try:
                    result = STAGE_FNS[sid](p, ctx)
                except Exception as exc:  # noqa: BLE001
                    log.exception("Stage %s failed", sid)
                    state["status"] = "failed"
                    state["notes"] = str(exc)
                    run.status = "failed"
                    run.error = f"{sid}: {exc}"
                    run.finished_at = utcnow()
                    p.status = "draft"
                    db.commit()
                    self._broadcast(project_id, "stage_failed", {"project_id": project_id, "stage_id": sid, "error": str(exc)})
                    self._broadcast(project_id, "run_finished", {"project_id": project_id, "status": "failed", "error": str(exc)})
                    return

                # small progressive ticks for realism
                ticks = 3
                for i in range(1, ticks + 1):
                    time.sleep(settings.PIPELINE_STAGE_SECONDS / ticks)
                    state["progress"] = round(i * 100 / ticks, 1)
                    run.last_heartbeat = utcnow()
                    db.commit()
                    self._broadcast(project_id, "stage_update", {"project_id": project_id, "stage_id": sid, "status": "running", "progress": state["progress"], "project_progress": self._progress(p)})

                p.outputs[sid] = result
                state["status"] = "completed"
                state["progress"] = 100
                state["completed_at"] = utcnow().isoformat()
                state["notes"] = f"Completed in {max(0.1, round(time.time() - t0, 2))}s"
                p.progress = self._progress(p)
                db.commit()
                self._broadcast(project_id, "stage_update", {"project_id": project_id, "stage_id": sid, "status": "completed", "progress": 100, "project_progress": p.progress})

            # pipeline finished → finalize
            p.status = "review" if "publishing" not in p.outputs else "published"
            p.progress = 100.0
            p.current_stage = ""
            run.status = "completed"
            run.stages_completed = len(STAGES) - start_idx
            run.finished_at = utcnow()
            db.commit()
            self._auto_render(db, p)
            self._broadcast(project_id, "run_finished", {"project_id": project_id, "status": "completed"})
        except Exception as exc:  # noqa: BLE001
            log.exception("Pipeline worker crashed")
            if run:
                run.status = "failed"
                run.error = str(exc)
                run.finished_at = utcnow()
            try:
                db.commit()
            except Exception:
                db.rollback()
            self._broadcast(project_id, "run_finished", {"project_id": project_id, "status": "failed", "error": str(exc)})
        finally:
            db.close()

    @staticmethod
    def _auto_render(db, p: Project) -> None:
        """Render the director's cut as soon as a run completes, so the
        project's Final film page always has a fresh playable video.
        Skips only when a render for this project is already running."""
        plan = (p.outputs or {}).get("video_generation") or {}
        if not plan.get("scenes"):
            return
        import uuid

        from sqlalchemy import select  # noqa: PLC0415

        from ..services.render import render_engine  # noqa: PLC0415

        jobs = db.scalars(
            select(RenderJob).where(RenderJob.project_id == p.id, RenderJob.owner_id == p.owner_id)
        ).all()
        if any(j.status in ("queued", "rendering") for j in jobs):
            return
        job = RenderJob(
            id=uuid.uuid4().hex,
            owner_id=p.owner_id,
            project_id=p.id,
            scene_label="Full timeline",
            model="auto",
            resolution="1080p",
            fps=30,
            priority=5,
            params={},
            status="queued",
        )
        db.add(job)
        db.commit()
        log.info("auto-rendering final film for %s (%s)", p.id, job.id)
        render_engine.start(job.id)

    @staticmethod
    def _progress(p: Project) -> float:
        done = sum(1 for s in p.stages.values() if s.get("status") == "completed")
        return round(done / len(STAGES) * 100, 1)

    # --------------------------------------------------------- publishing
    def publish(self, db, project: Project, platform: str, scheduled_at=None, meta=None) -> PublishEntry:
        """Record a platform publish (official-API adapter interface; mock
        adapters simulate the round trip)."""
        from datetime import datetime as dt

        scheduled = None
        if scheduled_at:
            try:
                scheduled = dt.fromisoformat(scheduled_at.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                scheduled = utcnow() + timedelta(hours=1)
        entry = PublishEntry(
            project_id=project.id,
            platform=platform,
            status="scheduled" if scheduled else "published",
            scheduled_at=scheduled,
            published_at=None if scheduled else utcnow(),
            url=f"https://{platform}.com/watch/cf-{project.id[:8]}",
            meta=meta or {},
        )
        db.add(entry)
        if not scheduled:
            # simulated audience response lands immediately
            stats = generators.simulate_analytics(project.id + platform)
            db.add(AnalyticsSnapshot(project_id=project.id, **{k: v for k, v in stats.items() if k in ("views", "watch_time_min", "avg_retention", "retention", "ctr", "revenue_usd", "daily")}))
            project.status = "published"
        db.commit()
        return entry

    # -------------------------------------------------------- websockets
    def _broadcast(self, project_id: str, event: str, payload: dict) -> None:
        try:
            from .ws import manager

            manager.broadcast_project(project_id, {"type": event, **payload})
        except Exception:  # noqa: BLE001
            pass


engine = PipelineEngine()
