"""Core relational models. Production data is mostly JSON documents on a
project (script, storyboard, shots, SEO …) — that keeps pipeline outputs
versionable and cheap to query; the reference schema for a fully normalized
deployment is documented in docs/DATABASE.md."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, utcnow


def new_id() -> str:
    return uuid.uuid4().hex


# Mutable JSON variants so in-place dict/list edits (pipeline stage state,
# outputs, etc.) are detected as dirty and persisted on commit.
JsonDict = MutableDict.as_mutable(JSON)
JsonList = MutableList.as_mutable(JSON)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="creator")  # viewer|creator|pro|admin
    plan: Mapped[str] = mapped_column(String(20), default="free")     # free|pro|studio|enterprise
    avatar_seed: Mapped[str] = mapped_column(String(16), default=lambda: uuid.uuid4().hex[:6])
    settings: Mapped[dict] = mapped_column(JsonDict, default=dict)    # audio defaults, prefs
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=utcnow)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Team(Base):
    __tablename__ = "teams"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=utcnow)


class TeamMember(Base):
    __tablename__ = "team_members"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(20), default="creator")
    joined_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=utcnow)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    team_id: Mapped[Optional[str]] = mapped_column(ForeignKey("teams.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    topic: Mapped[str] = mapped_column(String(255), default="")
    category: Mapped[str] = mapped_column(String(60), default="explainer")  # youtube|tiktok|documentary|...
    language: Mapped[str] = mapped_column(String(20), default="en")
    tone: Mapped[str] = mapped_column(String(40), default="cinematic")
    target_duration: Mapped[int] = mapped_column(Integer, default=120)  # seconds
    status: Mapped[str] = mapped_column(String(30), default="draft")
    # draft|pre_production|in_production|post_production|review|published
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    current_stage: Mapped[str] = mapped_column(String(60), default="")
    stages: Mapped[dict] = mapped_column(JsonDict, default=dict)   # stage_id -> state
    outputs: Mapped[dict] = mapped_column(JsonDict, default=dict)  # stage_id -> payload
    characters: Mapped[list] = mapped_column(JsonList, default=list)
    environments: Mapped[list] = mapped_column(JsonList, default=list)
    settings: Mapped[dict] = mapped_column(JsonDict, default=dict)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|running|completed|failed|stopped|cancelled
    stages_completed: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    start_stage: Mapped[str] = mapped_column(String(40), default="")
    worker_id: Mapped[str] = mapped_column(String(64), nullable=True, default=None)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Character(Base):
    __tablename__ = "characters"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    archetype: Mapped[str] = mapped_column(String(60), default="host")
    description: Mapped[str] = mapped_column(Text, default="")
    traits: Mapped[list] = mapped_column(JsonList, default=list)
    voice: Mapped[dict] = mapped_column(JsonDict, default=dict)
    expressions: Mapped[list] = mapped_column(JsonList, default=list)
    wardrobe: Mapped[list] = mapped_column(JsonList, default=list)
    palette: Mapped[list] = mapped_column(JsonList, default=list)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=utcnow)


class Environment(Base):
    __tablename__ = "environments"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(60), default="landmark")
    description: Mapped[str] = mapped_column(Text, default="")
    lighting: Mapped[dict] = mapped_column(JsonDict, default=dict)
    weather: Mapped[list] = mapped_column(JsonList, default=list)
    palette: Mapped[list] = mapped_column(JsonList, default=list)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=utcnow)


class RenderJob(Base):
    __tablename__ = "render_jobs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    scene_label: Mapped[str] = mapped_column(String(120), default="")
    model: Mapped[str] = mapped_column(String(80), default="auto")
    resolution: Mapped[str] = mapped_column(String(20), default="1080p")
    fps: Mapped[int] = mapped_column(Integer, default=30)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    priority: Mapped[int] = mapped_column(Integer, default=5)
    error: Mapped[str] = mapped_column(Text, default="")
    duration_s: Mapped[float] = mapped_column(Float, default=8.0)
    final_url: Mapped[str] = mapped_column(String(500), default="")
    assembled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    audio_report: Mapped[dict] = mapped_column(JsonDict, default=dict)
    params: Mapped[dict] = mapped_column(JsonDict, default=dict)   # image2video: seed_image, prompt, style, movement, …
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    worker_id: Mapped[str] = mapped_column(String(64), nullable=True, default=None)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Asset(Base):
    __tablename__ = "assets"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))  # logo|font|music|watermark|footage|intro|outro
    name: Mapped[str] = mapped_column(String(120))
    url: Mapped[str] = mapped_column(String(500), default="")
    meta: Mapped[dict] = mapped_column(JsonDict, default=dict)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=utcnow)


class VideoClip(Base):
    __tablename__ = "video_clips"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("render_jobs.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    scene_id: Mapped[str] = mapped_column(String(60), default="scene-1")
    clip_ref: Mapped[str] = mapped_column(String(80), default="clip")
    provider: Mapped[str] = mapped_column(String(40), default="kling-3.0")
    prompt: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="queued")
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quality: Mapped[dict] = mapped_column(JsonDict, default=dict)
    file_path: Mapped[str] = mapped_column(String(500), default="")
    thumb_path: Mapped[str] = mapped_column(String(500), default="")
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    fps: Mapped[int] = mapped_column(Integer, default=0)
    duration_s: Mapped[float] = mapped_column(Float, default=3.0)
    provider_meta: Mapped[dict] = mapped_column(JsonDict, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)


class PublishEntry(Base):
    __tablename__ = "publish_entries"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    platform: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    url: Mapped[str] = mapped_column(String(500), default="")
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    meta: Mapped[dict] = mapped_column(JsonDict, default=dict)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=utcnow)


class AnalyticsSnapshot(Base):
    __tablename__ = "analytics_snapshots"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    views: Mapped[int] = mapped_column(Integer, default=0)
    watch_time_min: Mapped[float] = mapped_column(Float, default=0.0)
    avg_retention: Mapped[float] = mapped_column(Float, default=0.0)
    ctr: Mapped[float] = mapped_column(Float, default=0.0)
    revenue_usd: Mapped[float] = mapped_column(Float, default=0.0)
    retention: Mapped[list] = mapped_column(JsonList, default=list)
    daily: Mapped[list] = mapped_column(JsonList, default=list)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    target: Mapped[str] = mapped_column(String(120), default="")
    detail: Mapped[dict] = mapped_column(JsonDict, default=dict)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=utcnow)


class Subscription(Base):
    __tablename__ = "subscriptions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    plan: Mapped[str] = mapped_column(String(20), default="free")
    status: Mapped[str] = mapped_column(String(20), default="active")
    renews_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    usage: Mapped[dict] = mapped_column(JsonDict, default=dict)


class ProviderKey(Base):
    """Encrypted AI-provider API keys, stored per user (Fernet at rest)."""
    __tablename__ = "provider_keys"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(40), index=True)
    encrypted_key: Mapped[str] = mapped_column(Text, default="")
    last4: Mapped[str] = mapped_column(String(8), default="")
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
