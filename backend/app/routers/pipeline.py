"""Pipeline control: run, status, run history, stage definitions."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import audit, get_current_user
from ..models import PipelineRun, Project, User
from ..schemas import RunPipelineIn
from ..services.pipeline import PHASES, STAGES, engine, initial_stages
from .projects import get_owned_project

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.get("/stages")
def stage_definitions(user: User = Depends(get_current_user)):
    return {"stages": STAGES, "phases": PHASES}


@router.get("/projects/{project_id}")
def pipeline_status(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = get_owned_project(project_id, user, db)
    if not p.stages:
        p.stages = initial_stages()
        db.commit()
    return {
        "project_id": p.id,
        "status": p.status,
        "progress": p.progress,
        "current_stage": p.current_stage,
        "running": engine.is_running(p.id),
        "stages": p.stages,
    }


@router.post("/projects/{project_id}/run")
def run_pipeline(project_id: str, body: RunPipelineIn | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = get_owned_project(project_id, user, db)
    start = body.start_stage if body else None
    if start and start not in [s["id"] for s in STAGES]:
        raise HTTPException(status_code=400, detail=f"Unknown stage '{start}'.")
    result = engine.start(p.id, start)
    if not result["started"]:
        raise HTTPException(status_code=409, detail=result["reason"])
    audit(db, user.id, "pipeline.run", p.id, {"start_stage": start})
    return {"started": True, "project_id": p.id, "start_stage": start}


@router.get("/projects/{project_id}/runs")
def run_history(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_owned_project(project_id, user, db)
    rows = db.scalars(
        select(PipelineRun).where(PipelineRun.project_id == project_id).order_by(PipelineRun.started_at.desc()).limit(25)
    ).all()
    return [
        {
            "id": r.id,
            "status": r.status,
            "stages_completed": r.stages_completed,
            "error": r.error,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        }
        for r in rows
    ]
