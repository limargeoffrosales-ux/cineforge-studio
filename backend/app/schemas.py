"""Pydantic request/response schemas."""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


class ProjectIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    topic: str = Field(default="", max_length=255)
    description: str = ""
    category: str = "explainer"
    language: str = "en"
    tone: str = "cinematic"
    target_duration: int = 120
    settings: Dict[str, Any] = {}


class ProjectPatch(BaseModel):
    title: Optional[str] = None
    topic: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    language: Optional[str] = None
    tone: Optional[str] = None
    target_duration: Optional[int] = None
    settings: Optional[Dict[str, Any]] = None


class RunPipelineIn(BaseModel):
    start_stage: Optional[str] = None  # resume from a specific stage


class CharacterIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    archetype: str = "host"
    description: str = ""
    traits: List[str] = []
    voice: Dict[str, Any] = {}
    expressions: List[str] = []
    wardrobe: List[str] = []
    palette: List[str] = []
    is_shared: bool = False


class EnvironmentIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: str = "landmark"
    description: str = ""
    lighting: Dict[str, Any] = {}
    weather: List[str] = []
    palette: List[str] = []
    is_shared: bool = False


class RenderJobIn(BaseModel):
    project_id: str
    scene_label: str = ""
    model: str = "cineforge-1.0"
    resolution: str = "1080p"
    fps: int = 30
    priority: int = 5
    duration_s: float = 8.0
    params: Dict[str, Any] = {}


class PublishIn(BaseModel):
    platform: str
    scheduled_at: Optional[str] = None
    meta: Dict[str, Any] = {}


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    project_id: Optional[str] = None


class TeamInviteIn(BaseModel):
    email: EmailStr
    role: str = "creator"


class UpgradeIn(BaseModel):
    plan: str = "pro"
