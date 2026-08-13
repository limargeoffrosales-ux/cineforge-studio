"""Video Generation Engine API — provider registry, benchmark, evaluation."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import get_current_user
from ..models import Project, User
from ..services.video.providers import PROVIDERS, PROVIDER_ORDER
from ..services.video.quality import best_angle, evaluate_spec
from ..services.video.router import ensemble_uplift, route_scene
from .projects import get_owned_project

router = APIRouter(prefix="/video", tags=["video"])

_KEY_ATTRS = {"veo-3.1": "VEO_API_KEY", "runway-gen-4.5": "RUNWAY_API_KEY", "kling-3.0": "KLING_API_KEY", "seedance-2.0": "SEEDANCE_API_KEY"}


def _provider_payload(spec) -> dict:
    return {
        "id": spec.id,
        "name": spec.name,
        "vendor": spec.vendor,
        "api": spec.api,
        "strengths": list(spec.strengths),
        "weaknesses": list(spec.weaknesses),
        "max_duration_s": spec.max_duration_s,
        "max_res": spec.max_res,
        "native_audio": spec.native_audio,
        "image_to_video": spec.image_to_video,
        "video_to_video": spec.video_to_video,
        "last_frame": spec.last_frame,
        "character_consistency": spec.character_consistency,
        "camera_control": spec.camera_control,
        "price_per_sec": spec.price_per_sec,
        "quality": spec.quality,
        "director_note": spec.director_note,
        "configured": bool(getattr(settings, _KEY_ATTRS.get(spec.id, ""), "")),
    }


@router.get("/providers")
def list_providers(user: User = Depends(get_current_user)):
    """Frontier model registry + the CineForge orchestration case."""
    from ..services.video.router import ensemble_uplift as _uplift

    providers = [_provider_payload(PROVIDERS[p]) for p in PROVIDER_ORDER]
    benchmark = {
        "per_model": [
            {"provider": p, "composite": round(sum(PROVIDERS[p].quality.values()) / len(PROVIDERS[p].quality) * 100, 1)}
            for p in PROVIDER_ORDER
        ],
        "ensemble": _uplift({"id": "benchmark"}),
    }
    return {"providers": providers, "benchmark": benchmark, "mode": "mock"}


@router.get("/benchmark")
def benchmark(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Per-scene routed benchmark for a specific project."""
    projects = db.query(Project).filter(Project.owner_id == user.id).order_by(Project.updated_at.desc()).limit(1).all()
    pid = projects[0].id if projects else "demo"
    return {"ensemble": ensemble_uplift({"id": pid})}


@router.post("/evaluate")
def evaluate(body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Quality-gate report for a scene's clips (director's review)."""
    project_id = body.get("project_id", "")
    scene_id = body.get("scene_id", "")
    p = get_owned_project(project_id, user, db)
    plan = p.outputs.get("video_generation") or {}
    scene = next((s for s in plan.get("scenes", []) if s.get("scene_id") == scene_id), None)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found in the video plan.")
    project_dict = {
        "id": p.id, "topic": p.topic, "tone": p.tone, "category": p.category,
        "language": p.language, "target_duration": p.target_duration,
        "characters": p.characters or [], "environments": p.environments or [],
    }
    reports = []
    for clip in scene.get("clips", []):
        shot = clip.get("shot", {})
        decision = clip.get("routing") or route_scene(shot, scene, project_dict)
        spec = {
            "clip_id": clip.get("clip_id", "clip"), "scene_id": scene_id,
            "provider": decision["chosen"], "prompt": clip.get("prompt", ""),
            "background": shot.get("background", ""), "time_of_day": shot.get("time_of_day", ""),
            "weather": shot.get("weather", ""), "character": p.characters[0] if p.characters else None,
        }
        reports.append({"clip_id": clip.get("clip_id"), **evaluate_spec(spec, decision["chosen"])})
    return {"scene_id": scene_id, "project_id": project_id, "clips": reports, "profile": best_angle(project_dict)}


@router.post("/image2video")
async def image2video(
    file: UploadFile = File(...),
    prompt: str = Form(""),
    duration_s: float = Form(8.0),
    style: str = Form("auto"),
    movement: str = Form("auto"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Image → video: upload a still, get a playable animated film back.
    Works fully offline (Ken Burns style animation, grade + grain)."""
    import io
    import uuid
    from pathlib import Path

    from PIL import Image

    from ..models import RenderJob
    from ..services.video.local import ensure_media_dir
    from ..services.render import render_engine

    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Upload an image file (PNG, JPEG, WebP…).")

    raw = await file.read()
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (max 25 MB).")

    try:
        with Image.open(io.BytesIO(raw)) as im:
            img = im.copy()
            if img.mode != "RGB":
                img = img.convert("RGB")
            w, h = img.size
            if max(w, h) > 1920:  # downscale huge stills to keep rendering fast
                s = 1920 / max(w, h)
                img = img.resize((int(w * s), int(h * s)), Image.LANCZOS)
    except Exception:
        raise HTTPException(status_code=400, detail="Could not decode image — unsupported format?")

    title = (prompt or "Image").strip().replace("\n", " ")[:60]
    project = Project(
        id=uuid.uuid4().hex,
        owner_id=user.id,
        topic=title,
        category="image2video",
        tone="cinematic",
        title=title,
        language="en",
        status="draft",
    )
    db.add(project)
    db.commit()

    job = RenderJob(
        id=uuid.uuid4().hex,
        owner_id=user.id,
        project_id=project.id,
        scene_label="Image",
        model="image",
        resolution="1080p",
        fps=30,
        priority=5,
        duration_s=max(2.0, min(15.0, duration_s)),
        params={
            "seed_image": "",
            "prompt": prompt,
            "style": style,
            "movement": movement,
            "lighting": "soft",
            "mood": "neutral",
        },
        status="queued",
    )
    db.add(job)
    db.commit()

    up_dir = ensure_media_dir() / "uploads" / user.id
    up_dir.mkdir(parents=True, exist_ok=True)
    seed_path = up_dir / f"img-{job.id}.jpg"
    img.save(seed_path, quality=92)
    job.params = {**job.params, "seed_image": str(seed_path)}
    db.commit()

    render_engine.start(job.id)

    from .ops import _job_payload

    return {"job_id": job.id, "project_id": project.id, **_job_payload(job, db)}
