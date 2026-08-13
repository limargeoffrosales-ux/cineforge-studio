"""Shared FastAPI dependencies: current user, RBAC guards, audit helper."""
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from .db import get_db
from .models import AuditLog, User
from .security import decode_token, role_at_least

AUTH_EXCEPTION = HTTPException(status_code=401, detail="Invalid or expired token")


def get_current_user(
    authorization: str = Header(default=""),
    x_api_key: str = Header(default=""),
    db: Session = Depends(get_db),
) -> User:
    """Authenticate via Bearer JWT or an API key (dev: API keys map to a
    seeded service account; production would look up keys in a vault table)."""
    if authorization.lower().startswith("bearer "):
        payload = decode_token(authorization[7:].strip())
        if not payload:
            raise AUTH_EXCEPTION
        user = db.get(User, payload.get("sub"))
        if not user:
            raise AUTH_EXCEPTION
        return user
    if x_api_key:
        # demo key store — see docs/API.md for the production design
        if x_api_key == "cf_live_demo_service_key":
            user = db.query(User).filter(User.email == "api@cineforge.ai").first()
            if user:
                return user
    raise AUTH_EXCEPTION


def require_role(minimum: str):
    def guard(user: User = Depends(get_current_user)) -> User:
        if not role_at_least(user.role, minimum):
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user

    return guard


def audit(db: Session, user_id: str, action: str, target: str = "", detail: dict | None = None) -> None:
    db.add(AuditLog(user_id=user_id, action=action, target=target, detail=detail or {}))
    db.commit()


class RateLimiter:
    """Tiny in-memory fixed-window limiter (per-IP). Swap for Redis in prod."""

    def __init__(self, limit: int):
        self.limit = limit
        self._hits: dict[str, list[float]] = {}

    def allow(self, key: str) -> bool:
        import time

        now = time.time()
        window = [t for t in self._hits.get(key, []) if now - t < 60.0]
        window.append(now)
        self._hits[key] = window
        return len(window) <= self.limit


rate_limiter = RateLimiter(240)


def check_rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    if not rate_limiter.allow(ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded — slow down, director.")
