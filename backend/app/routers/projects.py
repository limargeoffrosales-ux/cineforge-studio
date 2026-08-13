"""Projects CRUD + full project payload."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import audit, get_current_user
from ..models import Project, User
from ..schemas import ProjectIn, ProjectPatch

router = APIRouter(prefix="/projects", tags=["projects"])


def get_owned_project(project_id: str, user: User, db: Session) -> Project:
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found.")
    if p.owner_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="You don't have access to this project.")
    return p


def project_payload(p: Project, include_outputs: bool = False) -> dict:
    data = {
        "id": p.id,
        "owner_id": p.owner_id,
        "title": p.title,
        "description": p.description,
        "topic": p.topic,
        "category": p.category,
        "language": p.language,
        "tone": p.tone,
        "target_duration": p.target_duration,
        "status": p.status,
        "progress": p.progress,
        "current_stage": p.current_stage,
        "stages": p.stages,
        "characters": p.characters or [],
        "environments": p.environments or [],
        "settings": p.settings or {},
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }
    if include_outputs:
        data["outputs"] = p.outputs or {}
    return data


@router.get("")
def list_projects(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Project).where(Project.owner_id == user.id).order_by(Project.updated_at.desc()).limit(200)
    ).all()
    return [project_payload(p) for p in rows]


@router.post("")
def create_project(body: ProjectIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = Project(
        owner_id=user.id,
        title=body.title,
        topic=body.topic or body.title,
        description=body.description,
        category=body.category,
        language=body.language,
        tone=body.tone,
        target_duration=body.target_duration,
        settings=body.settings,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    audit(db, user.id, "project.create", p.id, {"title": p.title})
    return project_payload(p)


@router.get("/{project_id}")
def get_project(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = get_owned_project(project_id, user, db)
    return project_payload(p, include_outputs=True)


@router.patch("/{project_id}")
def patch_project(project_id: str, body: ProjectPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = get_owned_project(project_id, user, db)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(p, field, value)
    db.commit()
    db.refresh(p)
    audit(db, user.id, "project.update", p.id)
    return project_payload(p)


@router.delete("/{project_id}")
def delete_project(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = get_owned_project(project_id, user, db)
    db.delete(p)
    db.commit()
    audit(db, user.id, "project.delete", project_id)
    return {"ok": True}
