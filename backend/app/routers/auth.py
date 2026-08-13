"""Auth: register, login, me, demo seed info, API keys."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db, utcnow
from ..deps import audit, check_rate_limit, get_current_user
from ..models import AuditLog, Subscription, User
from ..schemas import LoginIn, RegisterIn, TokenOut
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_payload(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "name": u.name,
        "role": u.role,
        "plan": u.plan,
        "avatar_seed": u.avatar_seed,
    }


@router.post("/register", response_model=TokenOut, dependencies=[Depends(check_rate_limit)])
def register(body: RegisterIn, db: Session = Depends(get_db)):
    exists = db.scalar(select(User).where(User.email == body.email.lower()))
    if exists:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    user = User(
        email=body.email.lower(),
        name=body.name.strip(),
        password_hash=hash_password(body.password),
        role="creator",
        plan="free",
    )
    db.add(user)
    db.flush()
    db.add(Subscription(user_id=user.id, plan="free", usage={"ai_credits": 100, "renders": 5}))
    db.commit()
    audit(db, user.id, "auth.register", "user", {"email": user.email})
    return TokenOut(access_token=create_access_token(user.id, user.role), user=_user_payload(user))


@router.post("/login", response_model=TokenOut, dependencies=[Depends(check_rate_limit)])
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    user.last_login = utcnow()
    db.commit()
    audit(db, user.id, "auth.login", "user")
    return TokenOut(access_token=create_access_token(user.id, user.role), user=_user_payload(user))


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return _user_payload(user)


@router.get("/seed-info")
def seed_info(db: Session = Depends(get_db)):
    """Demo credentials for the evaluation environment (disabled in prod)."""
    demo = db.scalar(select(User).where(User.email == "demo@cineforge.ai"))
    return {
        "demo_available": bool(demo),
        "email": "demo@cineforge.ai",
        "password": "cineforge123",
        "note": "You can also register a fresh account.",
    }


@router.get("/api-keys")
def list_api_keys(user: User = Depends(get_current_user)):
    """Placeholder for the API-key manager. Production stores hashed keys in a
    vault table with per-key scopes, quotas and rotation."""
    return {"keys": [], "hint": "Create keys from the dashboard settings (Phase 2)."}


def get_or_create_service_user(db: Session) -> User:
    u = db.scalar(select(User).where(User.email == "api@cineforge.ai"))
    if not u:
        u = User(email="api@cineforge.ai", name="Service Account", password_hash=hash_password("not-a-real-password"), role="admin", plan="enterprise")
        db.add(u)
        db.commit()
    return u
