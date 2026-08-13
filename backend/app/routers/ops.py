"""Render queue, publishing, analytics, billing, teams, chat, admin."""
import math
import os
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db, utcnow
from ..deps import audit, get_current_user, require_role
from ..models import AnalyticsSnapshot, Asset, Character, Environment, Project, PublishEntry, RenderJob, Subscription, Team, TeamMember, User
from ..schemas import ChatIn, PublishIn, RenderJobIn, TeamInviteIn, UpgradeIn
from ..services.generators import PUBLISH_PLATFORMS
from ..services.pipeline import engine
from .projects import get_owned_project

router = APIRouter(tags=["ops"])


# ------------------------------------------------------------------ renders
@router.get("/render/jobs")
def list_render_jobs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(RenderJob).where(RenderJob.owner_id == user.id).order_by(RenderJob.created_at.desc()).limit(100)
    ).all()
    return [_job_payload(j, db) for j in rows]


def _media_url(path: str) -> str:
    """Absolute storage path → URL path relative to the /media mount.

    Always forward slashes — Windows os.sep would produce browser-breaking
    URLs like /media/clips\\clip.mp4.
    """
    if not path:
        return ""
    try:
        from ..services.video.local import MEDIA_ROOT

        rel = os.path.relpath(path, MEDIA_ROOT).replace(os.sep, "/")
        return f"/media/{rel}"
    except Exception:
        return ""


def _clip_payload(c: "VideoClip") -> dict:
    from ..models import VideoClip

    return {
        "id": c.id, "scene_id": c.scene_id, "clip_ref": c.clip_ref, "provider": c.provider,
        "status": c.status, "score": c.score, "prompt": c.prompt,
        "file_url": _media_url(c.file_path),
        "thumb_url": _media_url(c.thumb_path),
        "duration_s": c.duration_s, "width": c.width, "height": c.height,
        "error": c.error, "quality": c.quality, "provider_meta": c.provider_meta or {},
    }


def _job_payload(j: RenderJob, db: Session | None = None) -> dict:
    from ..models import VideoClip

    clips = []
    if db:
        clips = db.scalars(select(VideoClip).where(VideoClip.job_id == j.id).order_by(VideoClip.created_at)).all()
    return {
        "id": j.id, "project_id": j.project_id, "scene_label": j.scene_label,
        "model": j.model, "resolution": j.resolution, "fps": j.fps,
        "status": j.status, "progress": j.progress, "priority": j.priority,
        "error": j.error, "duration_s": j.duration_s,
        "final_url": _media_url(j.final_url),
        "assembled_at": j.assembled_at.isoformat() if j.assembled_at else None,
        "audio_report": j.audio_report or {},
        "clips": [_clip_payload(c) for c in clips],
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "finished_at": j.finished_at.isoformat() if j.finished_at else None,
    }


@router.post("/render/jobs")
def create_render_job(body: RenderJobIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_owned_project(body.project_id, user, db)
    import uuid

    from ..services.render import render_engine

    j = RenderJob(
        id=uuid.uuid4().hex,
        owner_id=user.id,
        project_id=body.project_id,
        scene_label=body.scene_label or "Full timeline",
        model=body.model,
        resolution=body.resolution,
        fps=body.fps,
        priority=min(10, max(1, body.priority)),
        duration_s=body.duration_s,
        params=body.params or {},
        status="queued",
    )
    db.add(j)
    db.commit()
    render_engine.start(j.id)
    audit(db, user.id, "render.enqueue", j.id, {"model": body.model, "resolution": body.resolution})
    return _job_payload(j, db)


@router.get("/render/jobs/{job_id}")
def get_render_job(job_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    j = db.get(RenderJob, job_id)
    if not j or j.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Job not found.")
    return _job_payload(j, db)


@router.post("/render/jobs/{job_id}/cancel")
def cancel_render(job_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    j = db.get(RenderJob, job_id)
    if not j or j.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Job not found.")
    if j.status not in ("completed", "failed", "assembled"):
        j.status = "cancelled"
        db.commit()
    return _job_payload(j, db)


@router.post("/render/jobs/{job_id}/assemble")
def assemble_render(job_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    j = db.get(RenderJob, job_id)
    if not j or j.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Job not found.")
    if j.status != "completed":
        raise HTTPException(status_code=409, detail="All clips must finish rendering first.")
    from ..services.render import render_engine

    render_engine.assemble(j.id)
    audit(db, user.id, "render.assemble", j.id)
    return {"started": True, "job_id": j.id}


@router.post("/render/jobs/{job_id}/clips/{clip_id}/reshoot")
def reshoot_clip(job_id: str, clip_id: str, body: dict | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Director loop: re-render one clip, optionally with an adjusted prompt
    or a different provider."""
    import threading

    from ..services.render import render_engine

    j = db.get(RenderJob, job_id)
    if not j or j.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Job not found.")
    clip = db.get(VideoClip, clip_id)
    if not clip or clip.job_id != job_id:
        raise HTTPException(status_code=404, detail="Clip not found.")
    provider = (body or {}).get("provider") or clip.provider
    prompt_override = (body or {}).get("prompt")
    t = threading.Thread(target=_reshoot_worker, args=(job_id, clip_id, provider, prompt_override), daemon=True)
    t.start()
    audit(db, user.id, "render.reshoot", clip_id, {"provider": provider})
    return {"started": True}


def _reshoot_worker(job_id: str, clip_id: str, provider: str, prompt_override: str | None) -> None:
    """Re-render a single clip row in place (director loop)."""
    from ..db import SessionLocal
    from ..models import Project, VideoClip
    from ..services.render import render_engine
    from ..services.video.local import render_clip
    from ..services.video.quality import evaluate_spec

    db = SessionLocal()
    try:
        clip = db.get(VideoClip, clip_id)
        if not clip:
            return
        project = db.get(Project, clip.project_id)
        clip.status = "rendering"
        clip.provider = provider
        if prompt_override:
            clip.prompt = prompt_override
        db.commit()
        spec = {
            "clip_id": clip.clip_ref, "scene_id": clip.scene_id, "job_id": job_id,
            "provider": provider, "prompt": clip.prompt, "duration_s": max(1.0, clip.duration_s or 3.0),
            "width": max(320, clip.width or 480), "height": max(180, clip.height or 270),
            "fps": max(12, clip.fps or 18), "seed": 42,
            "movement": "Orbit", "composition": "Wide", "camera": "Gimbal",
            "lighting": "Golden hour", "mood": "epic", "time_of_day": "golden hour",
            "weather": "clear", "background": "Banaue Rice Terraces — Golden Hour",
            "environment_category": "terraces",
            "palette": ["#d9a441", "#6b8f3a", "#2c3a2a"],
            "character": None,
        }
        try:
            result = render_clip(spec)
            clip.file_path = result["file"]
            clip.thumb_path = result.get("thumb", "")
            clip.status = "completed"
            clip.error = ""
        except Exception as exc:  # noqa: BLE001
            clip.status = "failed"
            clip.error = str(exc)[:300]
        q = evaluate_spec(spec, provider)
        clip.score = q["overall"]
        clip.quality = q
        clip.completed_at = utcnow()
        db.commit()
        if project:
            render_engine._broadcast(project.id, "clip_update", {"job_id": job_id, "clip_id": clip_id, "status": clip.status, "score": clip.score})
    finally:
        db.close()


# ---------------------------------------------------------------- publish
@router.get("/publish/platforms")
def publish_platforms(user: User = Depends(get_current_user)):
    return {"platforms": PUBLISH_PLATFORMS}


@router.get("/projects/{project_id}/publish")
def list_publish_entries(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_owned_project(project_id, user, db)
    rows = db.scalars(
        select(PublishEntry).where(PublishEntry.project_id == project_id).order_by(PublishEntry.created_at.desc())
    ).all()
    return [
        {
            "id": e.id, "platform": e.platform, "status": e.status, "url": e.url,
            "scheduled_at": e.scheduled_at.isoformat() if e.scheduled_at else None,
            "published_at": e.published_at.isoformat() if e.published_at else None,
            "meta": e.meta,
        }
        for e in rows
    ]


@router.post("/projects/{project_id}/publish")
def publish_project(project_id: str, body: PublishIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = get_owned_project(project_id, user, db)
    platform_ids = [x["id"] for x in PUBLISH_PLATFORMS]
    if body.platform not in platform_ids:
        raise HTTPException(status_code=400, detail=f"platform must be one of {platform_ids}")
    entry = engine.publish(db, p, body.platform, body.scheduled_at, body.meta)
    audit(db, user.id, "publish.dispatch", p.id, {"platform": body.platform, "scheduled": bool(body.scheduled_at)})
    return {
        "id": entry.id, "platform": entry.platform, "status": entry.status, "url": entry.url,
        "scheduled_at": entry.scheduled_at.isoformat() if entry.scheduled_at else None,
        "published_at": entry.published_at.isoformat() if entry.published_at else None,
    }


# -------------------------------------------------------------- analytics
@router.get("/analytics/overview")
def analytics_overview(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    snaps = db.scalars(select(AnalyticsSnapshot).join(Project, Project.id == AnalyticsSnapshot.project_id).where(Project.owner_id == user.id)).all()
    projects = db.scalars(select(Project).where(Project.owner_id == user.id)).all()
    published = db.scalars(select(PublishEntry).join(Project, Project.id == PublishEntry.project_id).where(Project.owner_id == user.id)).all()
    renders = db.scalars(select(RenderJob).where(RenderJob.owner_id == user.id)).all()
    total_views = sum(s.views for s in snaps)
    total_watch = sum(s.watch_time_min for s in snaps)
    total_revenue = sum(s.revenue_usd for s in snaps)
    # 14-day trend across snapshots (merged daily series)
    days: dict[str, dict] = {}
    for s in snaps:
        for d in (s.daily or []):
            day = d.get("day", "")
            if day:
                cur = days.setdefault(day, {"views": 0, "watch_min": 0})
                cur["views"] += d.get("views", 0)
                cur["watch_min"] += d.get("watch_min", 0)
    trend = [{"day": k, **v} for k, v in sorted(days.items())[-14:]]
    return {
        "totals": {
            "projects": len(projects),
            "published": len([e for e in published if e.status == "published"]),
            "renders_completed": len([r for r in renders if r.status == "completed"]),
            "views": total_views,
            "watch_time_min": round(total_watch),
            "revenue_usd": round(total_revenue, 2),
            "ai_credits_used": sum(1 for p in projects if p.outputs),
        },
        "trend": trend,
        "retention": snaps[-1].retention if snaps else [100] * 30,
        "platforms": [
            {"platform": e.platform, "status": e.status, "url": e.url, "published_at": e.published_at.isoformat() if e.published_at else None}
            for e in published[:20]
        ],
    }


@router.get("/projects/{project_id}/analytics")
def project_analytics(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_owned_project(project_id, user, db)
    snaps = db.scalars(
        select(AnalyticsSnapshot).where(AnalyticsSnapshot.project_id == project_id).order_by(AnalyticsSnapshot.created_at.desc())
    ).all()
    if not snaps:
        return {"empty": True}
    s = snaps[0]
    return {
        "empty": False,
        "views": s.views, "watch_time_min": s.watch_time_min, "avg_retention": s.avg_retention,
        "ctr": s.ctr, "revenue_usd": s.revenue_usd, "retention": s.retention, "daily": s.daily,
    }


# ----------------------------------------------------------------- billing
PLANS = {
    "free": {"price": 0, "credits": 100, "renders": 5, "max_res": "720p"},
    "pro": {"price": 29, "credits": 1500, "renders": 100, "max_res": "1080p"},
    "studio": {"price": 89, "credits": 6000, "renders": 500, "max_res": "4K"},
    "enterprise": {"price": 499, "credits": 50000, "renders": 10000, "max_res": "8K"},
}


@router.get("/billing/plan")
def billing_plan(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sub = db.scalar(select(Subscription).where(Subscription.user_id == user.id))
    return {
        "plan": user.plan,
        "limits": PLANS.get(user.plan, PLANS["free"]),
        "usage": (sub.usage if sub else {}) | {"projects": db.scalar(select(func.count(Project.id)).where(Project.owner_id == user.id)) or 0},
        "renews_at": sub.renews_at.isoformat() if sub and sub.renews_at else None,
    }


@router.post("/billing/upgrade")
def billing_upgrade(body: UpgradeIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.plan not in PLANS:
        raise HTTPException(status_code=400, detail=f"plan must be one of {list(PLANS)}")
    sub = db.scalar(select(Subscription).where(Subscription.user_id == user.id)) or Subscription(user_id=user.id)
    user.plan = body.plan
    sub.plan = body.plan
    sub.renews_at = utcnow() + timedelta(days=30)
    db.add(sub)
    db.commit()
    audit(db, user.id, "billing.upgrade", user.id, {"plan": body.plan})
    return {"plan": user.plan, "limits": PLANS[body.plan]}


# ------------------------------------------------------------------- teams
@router.get("/teams")
def list_teams(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Team).where((Team.owner_id == user.id) | (Team.id.in_(select(TeamMember.team_id).where(TeamMember.user_id == user.id))))
    ).all()
    return [
        {
            "id": t.id, "name": t.name, "owner_id": t.owner_id,
            "members": [
                {"user_id": m.user_id, "role": m.role}
                for m in db.scalars(select(TeamMember).where(TeamMember.team_id == t.id)).all()
            ],
        }
        for t in rows
    ]


@router.post("/teams")
def create_team(body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = Team(name=body.get("name", "New Studio Team"), owner_id=user.id)
    db.add(t)
    db.flush()
    db.add(TeamMember(team_id=t.id, user_id=user.id, role="admin"))
    db.commit()
    audit(db, user.id, "team.create", t.id, {"name": t.name})
    return {"id": t.id, "name": t.name, "owner_id": t.owner_id}


@router.post("/teams/{team_id}/invite")
def invite_member(team_id: str, body: TeamInviteIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = db.get(Team, team_id)
    if not t or t.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Team not found.")
    invitee = db.scalar(select(User).where(User.email == body.email.lower()))
    if not invitee:
        raise HTTPException(status_code=404, detail="User not found — invite links are a Phase 2 feature.")
    db.add(TeamMember(team_id=team_id, user_id=invitee.id, role=body.role))
    db.commit()
    audit(db, user.id, "team.invite", team_id, {"email": body.email, "role": body.role})
    return {"ok": True}


# -------------------------------------------------------------------- chat
CHAT_RULES = [
    ("publish", "Publishing is ready whenever the SEO stage is complete. From the Pipeline tab, open the Publishing stage and hit 'Publish now' — I'll push to YouTube, TikTok, Facebook or Instagram through their official APIs and generate the analytics snapshot."),
    ("render", "Open the Render Queue from the sidebar, then 'Enqueue render' to send scenes to the render farm. Each job simulates the provider round-trip; progress streams live."),
    ("stage|pipeline|progress", "You can re-run the whole pipeline or resume from any single stage — open your project, pick the stage you want to start from, and hit Run. Completed stages are kept; only the stages after the starting point are regenerated."),
    ("character", "Characters live in the Character Studio. Every project gets consistent digital actors with locked appearance keys, voice profiles and expression sets — you can also import shared characters from the library."),
    ("environment", "The Environment Builder ships with cinematic locations — Banaue Rice Terraces at golden hour, Vigan streets under overcast skies, Makati at cyberpunk night — each with lighting, weather and time-of-day presets."),
    ("script", "The Script stage writes a full three-act narration with per-scene dialogue, direction, transitions and audio cues. You can regenerate just the script from its stage card."),
    ("thumbnail|ctr", "The Thumbnail Studio generates three CTR-optimized concepts with composition, typography and palette analysis. Pick a winner, or ask me to iterate on contrast or emotion."),
    ("seo|tags|description", "The SEO stage generates titles, descriptions, tags, hashtags, chapters and keywords for every major platform — with the best chapter markers derived from your scene structure."),
    ("subscribe|plan|billing|price", "Plans: Free, Pro ($29), Studio ($89) and Enterprise ($499) — each unlocks more AI credits, render capacity and resolution. You can upgrade anytime from Settings → Billing."),
]


@router.post("/chat")
def chat(body: ChatIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    msg = body.message.lower()
    for key, reply in CHAT_RULES:
        if key in msg:
            return {"reply": reply}
    context = ""
    if body.project_id:
        p = get_owned_project(body.project_id, user, db)
        context = f" You're working on '{p.title}' — currently {p.progress}% through the pipeline."
    return {
        "reply": f"Great question{context}. I'm your AI production director: I can research, write scripts, storyboard, design characters and environments, plan shots, orchestrate rendering, edit, add motion graphics, subtitles, thumbnails, SEO and publishing. Tell me what you'd like to do next — for example, \"run the pipeline from the storyboard stage\"."
    }


# ------------------------------------------------------------------- admin
@router.get("/admin/stats")
def admin_stats(user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    return {
        "users": db.scalar(select(func.count(User.id))) or 0,
        "projects": db.scalar(select(func.count(Project.id))) or 0,
        "characters": db.scalar(select(func.count(Character.id))) or 0,
        "environments": db.scalar(select(func.count(Environment.id))) or 0,
        "assets": db.scalar(select(func.count(Asset.id))) or 0,
        "render_jobs": db.scalar(select(func.count(RenderJob.id))) or 0,
    }
