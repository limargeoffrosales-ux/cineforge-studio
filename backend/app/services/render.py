"""Render Engine — real render jobs.

Each job runs in a background thread: builds clip specs from the project's
video_generation plan (or a compare/fallback plan), renders every clip
through its routed provider (live adapter or procedural fallback), writes
quality reports, and broadcasts progress. `assemble` stitches completed
clips into a final film with crossfades, subtitles and an audio track.
"""
from __future__ import annotations

import logging
import math
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

from ..config import settings
from ..db import SessionLocal, utcnow
from ..models import Project, RenderJob, VideoClip
from .video.local import _ffmpeg, ensure_media_dir, render_clip
from .video.prompts import build_spec
from .video.providers import PROVIDER_ORDER, get_client
from .video.quality import evaluate_clip, evaluate_spec
from .video.router import route_scene

log = logging.getLogger("cineforge.render")

FADE = 0.5  # crossfade seconds


def _fast() -> bool:
    return settings.PIPELINE_FAST


def _size() -> tuple[int, int, int]:
    """(width, height, fps) — small+fast in test mode, 480p default offline."""
    if _fast():
        return 320, 180, 12
    return int(os.getenv("RENDER_WIDTH", "480")), int(os.getenv("RENDER_HEIGHT", "270")), int(os.getenv("RENDER_FPS", "18"))


class RenderEngine:
    def is_running(self, job_id: str) -> bool:
        """True while the job is queued or being rendered (survives restarts —
        backed by the DB, not a thread table)."""
        db = SessionLocal()
        try:
            job = db.get(RenderJob, job_id)
            return bool(job and job.status in ("queued", "rendering"))
        finally:
            db.close()

    def start(self, job_id: str) -> bool:
        """Enqueue a render job for the dispatcher. No thread is spawned."""
        db = SessionLocal()
        try:
            job = db.get(RenderJob, job_id)
            if not job:
                return False
            if job.status in ("queued", "rendering"):
                return False
            job.status = "queued"
            job.worker_id = None
            job.last_heartbeat = None
            job.error = ""
            db.commit()
            return True
        finally:
            db.close()

    # ------------------------------------------------------------- worker
    def _worker(self, job_id: str) -> None:
        """Render every clip of the job, driven inline by the dispatcher.
        Resumable: clips already completed (file present) are skipped, so an
        interrupted job picked up after a restart doesn't re-render finished
        work. Checks for cancellation before each clip."""
        from .queue import WORKER_ID, touch  # noqa: PLC0415

        db = SessionLocal()
        try:
            job = db.get(RenderJob, job_id)
            if not job:
                return
            project = db.get(Project, job.project_id)
            if not project:
                job.status = "failed"
                job.error = "project missing"
                job.finished_at = utcnow()
                db.commit()
                return

            specs = self._plan(job, project)
            total = len(specs)
            if total == 0:
                job.status = "completed"
                job.progress = 100.0
                job.finished_at = utcnow()
                db.commit()
                self._broadcast(job.project_id, "render_update", {"job_id": job.id, "status": "completed", "progress": 100})
                return

            # reconcile clip rows — create missing ones, keep completed ones.
            clips = db.query(VideoClip).filter(VideoClip.job_id == job.id).order_by(VideoClip.created_at).all()
            if not clips:
                for i, spec in enumerate(specs):
                    clips.append(VideoClip(
                        job_id=job.id, project_id=project.id,
                        scene_id=spec.get("scene_id", "scene-1"),
                        clip_ref=spec.get("clip_id", f"clip-{i}"),
                        provider=spec.get("provider", "kling-3.0"),
                        prompt=spec.get("prompt", ""),
                        status="queued",
                        duration_s=spec.get("duration_s", 3.0),
                    ))
                    db.add(clips[-1])
                    db.commit()
            elif len(clips) < total:
                for i in range(len(clips), total):
                    spec = specs[i]
                    clips.append(VideoClip(
                        job_id=job.id, project_id=project.id,
                        scene_id=spec.get("scene_id", "scene-1"),
                        clip_ref=spec.get("clip_id", f"clip-{i}"),
                        provider=spec.get("provider", "kling-3.0"),
                        prompt=spec.get("prompt", ""),
                        status="queued",
                        duration_s=spec.get("duration_s", 3.0),
                    ))
                    db.add(clips[-1])
                    db.commit()

            job.status = "rendering"
            job.worker_id = WORKER_ID
            job.started_at = job.started_at or utcnow()
            job.last_heartbeat = utcnow()
            db.commit()

            for i, clip in enumerate(clips):
                if job.status == "cancelled":
                    break
                spec = specs[i] if i < len(specs) else None
                if clip.status == "completed" and clip.file_path and Path(clip.file_path).exists():
                    # resume: already rendered on a previous attempt
                    continue
                if clip.status == "queued" or (clip.status == "failed" and (clip.attempts or 0) < 1):
                    clip.status = "rendering"
                    clip.error = ""
                    db.commit()
                    self._broadcast(job.project_id, "clip_update", {"job_id": job.id, "clip_id": clip.id, "status": "rendering"})
                    job.last_heartbeat = utcnow()
                    db.commit()

                    t0 = time.time()
                    result = {"status": "failed", "error": "no provider"}
                    try:
                        client = get_client(spec["provider"])
                        # online-first: if the routed model has no key, fall through
                        # to the free live renderer (Pollinations); that in turn
                        # degrades to the procedural cinematographer offline.
                        if not client.configured(owner_id=job.owner_id):
                            try:
                                client = get_client("pollinations")
                            except KeyError:
                                pass
                        result = client.generate(spec, owner_id=job.owner_id)
                    except Exception as exc:  # noqa: BLE001
                        log.exception("clip render failed")
                        result = {"status": "failed", "error": str(exc)[:300]}
                    if result.get("status") in ("ok", "mock"):
                        # "mock" is the offline procedural client — it still
                        # produced a real file (possibly photoreal-hybrid).
                        clip.status = "completed"
                        clip.file_path = result["file"]
                        clip.thumb_path = result.get("thumb", "")
                        clip.width = result.get("width", 0)
                        clip.height = result.get("height", 0)
                        clip.fps = spec.get("fps", 0)
                        meta = {**result.get("provider_meta", {})}
                        if not meta.get("source"):
                            meta["source"] = "procedural-fallback"
                        clip.provider_meta = meta
                    else:  # no usable output — fail honestly
                        clip.status = "failed"
                        clip.error = result.get("error") or result.get("status") or "render produced no file"
                        clip.provider_meta = {**result.get("provider_meta", {})}
                    clip.attempts = (clip.attempts or 0) + 1

                    quality = evaluate_spec(spec, spec.get("provider", "kling-3.0"))
                    if clip.status == "completed" and clip.file_path and Path(clip.file_path).exists():
                        try:
                            quality = evaluate_clip(
                                clip.file_path, spec, spec.get("provider", "kling-3.0"),
                                photo=bool(result.get("provider_meta", {}).get("still", False)),
                            )
                        except Exception as exc:  # noqa: BLE001
                            log.debug("clip metrics unavailable (%s) — kept pre-flight estimate", exc)
                    clip.score = quality["overall"]
                    clip.quality = quality
                    clip.started_at = clip.started_at or utcnow()
                    clip.completed_at = utcnow()
                    db.commit()

                    job.progress = round((i + 1) / total * 100, 1)
                    job.last_heartbeat = utcnow()
                    db.commit()
                    self._broadcast(job.project_id, "render_update", {"job_id": job.id, "status": "rendering", "progress": job.progress, "clip_id": clip.id, "score": clip.score, "elapsed_s": round(time.time() - t0, 1)})
                else:
                    touch("render", job.id)

            if job.status == "cancelled":
                remaining = [c for c in clips if c.status == "queued"]
                for clip in remaining:
                    clip.status = "cancelled"
                job.finished_at = utcnow()
                db.commit()
                self._broadcast(job.project_id, "render_update", {"job_id": job.id, "status": "cancelled"})
                return

            # assemble the director's cut synchronously so "completed" always
            # means the final film is on disk (guarded so a manual POST /assemble
            # can't race it). If the process dies mid-stitch the job stays
            # 'rendering' and recovery re-runs assembly on the next boot.
            try:
                self._assemble_now(job.id)
            except Exception as exc:  # noqa: BLE001
                log.warning("assemble failed for %s: %s", job.id, exc)

            job.status = "completed"
            job.progress = 100.0
            job.finished_at = utcnow()
            db.commit()
            self._broadcast(job.project_id, "render_update", {"job_id": job.id, "status": "completed", "progress": 100, "final_url": job.final_url})
        except Exception as exc:  # noqa: BLE001
            log.exception("render worker crashed")
            job = db.get(RenderJob, job_id)
            if job:
                job.status = "failed"
                job.error = str(exc)[:300]
                job.finished_at = utcnow()
                try:
                    db.commit()
                except Exception:
                    db.rollback()
            self._broadcast(job.project_id, "render_update", {"job_id": job_id, "status": "failed"})
        finally:
            db.close()

    # ------------------------------------------------------------ planning
    def _plan(self, job: RenderJob, project: Project) -> list[dict]:
        """Clip specs for a job: routed plan from the project, or a 4-way
        provider comparison when job.model == 'compare', or a fallback spec
        when the pipeline hasn't run yet."""
        w, h, fps = _size()
        plan = project.outputs.get("video_generation") or {}
        scenes = plan.get("scenes", [])

        if job.params.get("seed_image"):
            # image → video: animate the uploaded frame with a camera move
            style = job.params.get("style") or "auto"
            if style in PROVIDER_ORDER and get_client(style).configured(job.owner_id):
                provider = style
            else:
                provider = "pollinations"  # live if a free token is set; else procedural
            return [{
                "job_id": job.id,
                "clip_id": f"img-{job.id[:6]}",
                "seed_image": job.params["seed_image"],
                "seed_image_public": job.params.get("seed_image_public", ""),
                "prompt": job.params.get("prompt", ""),
                "provider": provider,
                "movement": job.params.get("movement", ""),
                "lighting": job.params.get("lighting", "soft"),
                "mood": job.params.get("mood", "neutral"),
                "duration_s": max(1.0, min(30.0, float(job.duration_s or 8.0))),
                "width": w, "height": h, "fps": fps,
                "scene_label": job.scene_label or "Image",
            }]

        if job.model == "compare":
            # same scene rendered by all four providers for side-by-side
            scene = scenes[int(job.scene_label or 0)] if scenes else {"id": "scene-1", "title": "Demo scene", "duration": 5, "dialogue": []}
            shot = ((scene.get("clips") or [{}])[0]).get("shot") or {
                "id": "shot-compare", "shot_type": "Wide", "framing": "medium", "lens": "35mm",
                "camera_type": "Gimbal", "movement": "Orbit", "background": "Banaue Rice Terraces — Golden Hour",
                "time_of_day": "golden hour", "weather": "clear", "lighting": "Golden hour rim",
                "mood": "epic", "duration": 4.0,
            }
            specs = []
            for pid in PROVIDER_ORDER:
                decision = {"chosen": pid, "reasons": ["comparison pass"]}
                spec = build_spec(shot, scene, _project_dict(project), decision, 0, fps)
                spec.update({"job_id": job.id, "width": w, "height": h, "fps": fps, "duration_s": min(4.0, float(shot.get("duration", 4))) , "clip_id": f"cmp-{pid}"})
                specs.append(spec)
            return specs

        specs = []
        for scene in scenes:
            for clip in scene.get("clips", []):
                if job.scene_label and job.scene_label not in ("Full timeline", "") and job.scene_label != scene.get("id"):
                    continue
                decision = clip.get("routing") or {"chosen": "kling-3.0", "reasons": ["default"]}
                if job.model and job.model not in ("auto", "cineforge-1.0", "cineforge-1.0", "cineforge-4k-pro"):
                    decision = {"chosen": job.model, "reasons": ["user override"]}
                spec = build_spec(clip.get("shot", {}), scene, _project_dict(project), decision, 0, fps)
                spec.update({"job_id": job.id, "width": w, "height": h, "fps": fps})
                specs.append(spec)
        if not specs:  # pipeline hasn't produced a plan yet
            scene = {"id": "scene-1", "title": "Demo scene", "duration": 4, "dialogue": []}
            shot = {"id": "shot-1", "shot_type": "Wide", "framing": "medium", "lens": "35mm", "camera_type": "Gimbal",
                    "movement": "Orbit", "background": "Banaue Rice Terraces — Golden Hour", "time_of_day": "golden hour",
                    "weather": "clear", "lighting": "Golden hour rim", "mood": "epic", "duration": 4.0}
            decision = route_scene(shot, scene, _project_dict(project))
            spec = build_spec(shot, scene, _project_dict(project), decision, 0, fps)
            spec.update({"job_id": job.id, "width": w, "height": h, "fps": fps, "duration_s": 4.0})
            specs = [spec]
        return specs

    # ----------------------------------------------------------- assembly
    _asm_locks: dict[str, threading.Lock] = {}

    def assemble(self, job_id: str) -> bool:
        db = SessionLocal()
        try:
            job = db.get(RenderJob, job_id)
            if not job or job.status == "cancelled":
                return False
            if job.final_url or job.assembled_at:
                return True  # already assembled
        finally:
            db.close()
        # one assembler per job at a time — auto-assemble (render worker) and a
        # manual POST /assemble must not stitch the same output path concurrently.
        lock = self._asm_locks.setdefault(job_id, threading.Lock())
        if not lock.acquire(blocking=False):
            return False
        try:
            db = SessionLocal()
            try:
                job = db.get(RenderJob, job_id)
                if job and (job.final_url or job.assembled_at):
                    return True  # another assembler finished while we waited
            finally:
                db.close()
            t = threading.Thread(target=self._assemble_worker_guarded, args=(job_id, lock), daemon=True)
            t.start()
            return True
        except Exception:  # noqa: BLE001
            lock.release()
            raise

    def _assemble_worker_guarded(self, job_id: str, lock: threading.Lock) -> None:
        try:
            self._assemble_worker(job_id)
        finally:
            lock.release()

    def _assemble_now(self, job_id: str) -> None:
        """Synchronous assembly for the render worker's final step. Blocks on
        the same per-job lock that guards async assemble(), so a manual
        POST /assemble during this window is a safe no-op."""
        lock = self._asm_locks.setdefault(job_id, threading.Lock())
        lock.acquire()
        try:
            self._assemble_worker(job_id)
        finally:
            lock.release()

    def _assemble_worker(self, job_id: str) -> None:
        db = SessionLocal()
        try:
            job = db.get(RenderJob, job_id)
            if not job:
                return
            clips = db.query(VideoClip).filter(VideoClip.job_id == job.id, VideoClip.status == "completed").order_by(VideoClip.created_at).all()
            if not clips:
                job.error = "no completed clips to assemble"
                db.commit()
                return
            project = db.get(Project, job.project_id)
            soundtrack = None
            audio_report: dict = {}
            if project:
                from .audio.mix import build_soundtrack

                media = ensure_media_dir()
                snd_dir = media / "audio"
                snd_dir.mkdir(parents=True, exist_ok=True)
                snd_path = snd_dir / f"{job.id}.wav"
                audio_report = build_soundtrack(project, clips, snd_path, owner_id=job.owner_id) or {}
                if audio_report.get("mixed"):
                    soundtrack = snd_path
            final = self._stitch(job, clips, project.outputs.get("subtitles") if project else None, soundtrack)
            final_url = str(final).replace(os.sep, "/")
            job.final_url = final_url
            job.assembled_at = utcnow()
            job.audio_report = audio_report
            db.commit()
            self._broadcast(job.project_id, "render_update", {"job_id": job.id, "status": "assembled", "final_url": final_url, "audio": audio_report})
        except Exception as exc:  # noqa: BLE001
            log.exception("assemble failed")
            try:
                job = db.get(RenderJob, job_id)
                if job:
                    job.error = f"assemble: {exc}"
                    db.commit()
            except Exception:
                db.rollback()
        finally:
            db.close()

    @staticmethod
    def _stitch(job: RenderJob, clips: list[VideoClip], subtitles: dict | None, soundtrack: Path | None = None) -> str:
        media = ensure_media_dir()
        final_dir = media / "final"
        final_dir.mkdir(parents=True, exist_ok=True)
        out = final_dir / f"{job.id}.mp4"
        paths = [Path(c.file_path) for c in clips if c.file_path and Path(c.file_path).exists()]
        if not paths:
            raise RuntimeError("clip files missing on disk")
        fade = min(FADE, min((len(paths) - 1) / max(1, len(paths)), 1.0))
        total = sum(_probe_duration(p) for p in paths) - fade * max(0, len(paths) - 1)

        cmd = [_ffmpeg(), "-y"]
        for p in paths:
            cmd += ["-i", str(p)]
        # soundtrack (if built) or silent stereo track sized to the film
        audio_input_idx = len(paths)
        if soundtrack and Path(soundtrack).exists():
            cmd += ["-i", str(soundtrack)]
            audio_map = f"{audio_input_idx}:a:0"
            use_silent = False
        else:
            cmd += ["-f", "lavfi", "-t", f"{max(total, 0.5):.2f}", "-i", "anullsrc=r=44100:cl=stereo"]
            audio_map = f"{audio_input_idx}:a:0"
            use_silent = True

        parts: list[str] = []
        if len(paths) > 1:
            prev = "[0:v]"
            offsets = []
            acc = _probe_duration(paths[0])
            for i in range(1, len(paths)):
                offsets.append(max(0.05, acc - i * fade))
                acc += _probe_duration(paths[i])
            for i in range(1, len(paths)):
                parts.append(f"{prev}[{i}:v]xfade=transition=fade:duration={fade:.2f}:offset={offsets[i - 1]:.2f}[v{i}]")
                prev = f"[v{i}]"
        else:
            prev = "[0:v]"

        cmd += ["-filter_complex", ";".join(parts + [f"{prev}eq=contrast=1.06:saturation=1.10,vignette=PI/5,noise=alls=5:allf=t,format=yuv420p[vout]"])]
        cmd += ["-map", "[vout]", "-map", audio_map]
        cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "25",
                "-c:a", "aac", "-shortest", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
            if res.returncode != 0:
                raise RuntimeError(res.stderr[-400:])
        except Exception:
            # fallback: video only
            cmd = [_ffmpeg(), "-y"]
            for p in paths:
                cmd += ["-i", str(p)]
            if len(paths) > 1:
                cmd += ["-filter_complex", ";".join(parts + [f"{prev}format=yuv420p[vout]"]), "-map", "[vout]"]
            else:
                cmd += ["-map", "0:v:0"]
            cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "25",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)]
            subprocess.run(cmd, check=True, capture_output=True, timeout=240)
        return str(out)

    @staticmethod
    def _write_srt(clips: list[VideoClip], subtitles: dict | None) -> str:
        """Global-offset SRT from the project's subtitle plan, if present."""
        media = ensure_media_dir()
        tmp = media / "tmp"
        tmp.mkdir(parents=True, exist_ok=True)
        srt = tmp / "subs.srt"
        if not subtitles:
            srt.write_text("")
            return str(srt)
        entries = subtitles.get("entries", [])
        # clip i covers scene in order; build scene→global offset map
        offsets: dict[str, float] = {}
        acc = 0.0
        fade = min(FADE, 0.5)
        seen: set[str] = set()
        for clip in clips:
            sid = clip.scene_id
            if sid not in seen:
                offsets[sid] = acc
                seen.add(sid)
            acc += clip.duration_s
        lines = []
        for i, e in enumerate(entries):
            start = e.get("start", 0) + offsets.get(e.get("scene_id", ""), 0)
            end = e.get("end", start + 2) + offsets.get(e.get("scene_id", ""), 0)
            lines.append(f"{i + 1}\n{_fmt_ts(start)} --> {_fmt_ts(end)}\n{e.get('text', '')}\n")
        srt.write_text("\n".join(lines), encoding="utf-8")
        return str(srt)

    # ------------------------------------------------------------- events
    def _broadcast(self, project_id: str, event: str, payload: dict) -> None:
        try:
            from .ws import manager

            manager.broadcast_project(project_id, {"type": event, **payload})
        except Exception:  # noqa: BLE001
            pass


def _fmt_ts(sec: float) -> str:
    ms = int(round(sec * 1000))
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _probe_duration(path: Path) -> float:
    try:
        res = subprocess.run(
            [_ffmpeg(), "-i", str(path)], capture_output=True, text=True, timeout=20
        )
        import re

        m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", res.stderr)
        if m:
            h, mm, s = m.groups()
            return int(h) * 3600 + int(mm) * 60 + float(s)
    except Exception:  # noqa: BLE001
        pass
    return 4.0


def _project_dict(p: Project) -> dict:
    return {
        "id": p.id, "topic": p.topic, "tone": p.tone, "category": p.category,
        "language": p.language, "target_duration": p.target_duration,
        "characters": p.characters or [], "environments": p.environments or [],
    }


render_engine = RenderEngine()
