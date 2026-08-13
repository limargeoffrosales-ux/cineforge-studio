"""CineForge AI Studio — FastAPI application entrypoint.

Run:  uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .config import settings as cfg
from .db import Base, SessionLocal, engine
from .models import User
from .routers import auth, library, ops, pipeline, projects, settings as settings_router, video
from .seed import seed
from .security import decode_token
from .services.ws import manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("cineforge")


def _migrate() -> None:
    """Tiny additive migrations for pre-existing SQLite stores (new columns)."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if not insp.has_table("render_jobs"):
        return  # fresh DB — create_all() builds everything

    def _add(table: str, col: str, ddl: str) -> None:
        if col not in {c["name"] for c in insp.get_columns(table)}:
            with engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
                conn.commit()
            log.info("migration: %s.%s added", table, col)

    _add("render_jobs", "params", "JSON DEFAULT '{}'")
    for table in ("render_jobs", "pipeline_runs"):
        _add(table, "worker_id", "VARCHAR(64)")
        _add(table, "attempts", "INTEGER DEFAULT 0")
        _add(table, "max_attempts", "INTEGER DEFAULT 3")
        _add(table, "last_heartbeat", "DATETIME")
    _add("pipeline_runs", "start_stage", "VARCHAR(40) DEFAULT ''")
    _add("video_clips", "attempts", "INTEGER DEFAULT 0")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _migrate()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()
    from .services.queue import start_dispatcher, stop_dispatcher

    start_dispatcher()
    log.info("%s v%s ready — LLM %s (queue worker %s)", cfg.APP_NAME, cfg.APP_VERSION, "LIVE" if cfg.llm_enabled else "MOCK MODE", "on")
    try:
        yield
    finally:
        stop_dispatcher()


app = FastAPI(
    title=cfg.APP_NAME,
    version=cfg.APP_VERSION,
    description="Enterprise AI video production platform — research, script, storyboard, direct, render, edit, publish.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tightened by the reverse proxy in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(pipeline.router)
app.include_router(library.router)
app.include_router(ops.router)
app.include_router(video.router)
app.include_router(settings_router.router)


@app.get("/healthz")
def healthz():
    return {"ok": True, "app": cfg.APP_NAME, "version": cfg.APP_VERSION, "mode": "llm" if cfg.llm_enabled else "mock"}


# rendered media (clips, finals, thumbs) — auth is enforced at the API layer;
# production swaps this for CDN + presigned URLs
import os as _os

_os.makedirs(cfg.MEDIA_DIR, exist_ok=True)
from fastapi.staticfiles import StaticFiles

app.mount("/media", StaticFiles(directory=cfg.MEDIA_DIR), name="media")


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, token: str = ""):
    user = None
    try:
        payload = decode_token(token)
        if not payload:
            await ws.close(code=4401, reason="Invalid token")
            return
        db: Session = SessionLocal()
        user = db.get(User, payload.get("sub"))
        db.close()
        if not user:
            await ws.close(code=4401, reason="Unknown user")
            return
        await manager.connect(ws, token, user.id)
        while True:
            msg = await ws.receive_json()
            if msg.get("type") == "subscribe" and msg.get("project_id"):
                manager.subscribe(user.id, msg["project_id"])
                await ws.send_json({"type": "subscribed", "project_id": msg["project_id"]})
            elif msg.get("type") == "unsubscribe" and msg.get("project_id"):
                manager.unsubscribe(user.id, msg["project_id"])
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        log.debug("ws error: %s", exc)
    finally:
        if user:
            await manager.disconnect(user.id)
