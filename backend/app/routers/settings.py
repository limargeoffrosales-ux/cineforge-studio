"""Settings — AI provider keys (encrypted at rest) + audio defaults."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings as app_settings
from ..db import get_db, utcnow
from ..deps import get_current_user
from ..models import ProviderKey, User
from ..services.audio.providers import VOICE_CATALOG
from ..services.vault import decrypt_secret, encrypt_secret, masked

router = APIRouter(prefix="/settings", tags=["settings"])

# provider catalog: id → (kind, name, env var for fallback config)
PROVIDER_CATALOG = {
    "veo-3.1": {"kind": "video", "name": "Google Veo 3.1", "env": "VEO_API_KEY"},
    "runway-gen-4.5": {"kind": "video", "name": "Runway Gen-4.5", "env": "RUNWAY_API_KEY"},
    "kling-3.0": {"kind": "video", "name": "Kling AI 3.0", "env": "KLING_API_KEY"},
    "seedance-2.0": {"kind": "video", "name": "ByteDance Seedance 2.0", "env": "SEEDANCE_API_KEY"},
    "pollinations": {"kind": "video", "name": "Pollinations Live (free — Wan 2.6 / Seedance)", "env": "POLLINATIONS_API_KEY"},
    "openai": {"kind": "llm", "name": "OpenAI (LLM + TTS)", "env": "OPENAI_API_KEY"},
    "elevenlabs": {"kind": "tts", "name": "ElevenLabs TTS", "env": "ELEVENLABS_API_KEY"},
}


def _key_for(user: User, provider: str, db: Session) -> str | None:
    """DB key takes priority, env var as fallback."""
    row = db.scalar(select(ProviderKey).where(ProviderKey.user_id == user.id, ProviderKey.provider == provider))
    if row and row.encrypted_key:
        try:
            return decrypt_secret(row.encrypted_key)
        except Exception:  # noqa: BLE001
            return None
    env_attr = PROVIDER_CATALOG.get(provider, {}).get("env")
    return getattr(app_settings, env_attr, "") or None if env_attr else None


@router.get("/providers")
def list_provider_settings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    out = []
    for pid, meta in PROVIDER_CATALOG.items():
        row = db.scalar(select(ProviderKey).where(ProviderKey.user_id == user.id, ProviderKey.provider == pid))
        env_configured = bool(getattr(app_settings, meta["env"], ""))
        db_value = row.encrypted_key if row else ""
        out.append(
            {
                "id": pid,
                "name": meta["name"],
                "kind": meta["kind"],
                "configured": bool(db_value) or env_configured,
                "source": "db" if db_value else ("env" if env_configured else "none"),
                "last4": row.last4 if row else "",
                "env_configured": env_configured,
            }
        )
    return {"providers": out}


@router.put("/providers/{provider}")
def save_provider_key(provider: str, body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if provider not in PROVIDER_CATALOG:
        raise HTTPException(status_code=400, detail=f"Unknown provider '{provider}'")
    key = (body.get("key") or "").strip()
    if len(key) < 8:
        raise HTTPException(status_code=400, detail="Key too short — refusing to store.")
    row = db.scalar(select(ProviderKey).where(ProviderKey.user_id == user.id, ProviderKey.provider == provider))
    if not row:
        row = ProviderKey(user_id=user.id, provider=provider)
        db.add(row)
    row.encrypted_key = encrypt_secret(key)
    row.last4 = masked(key)
    row.updated_at = utcnow()
    db.commit()
    return {"id": provider, "configured": True, "last4": row.last4}


@router.delete("/providers/{provider}")
def delete_provider_key(provider: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(ProviderKey).where(ProviderKey.user_id == user.id, ProviderKey.provider == provider))
    if row:
        db.delete(row)
        db.commit()
    return {"id": provider, "configured": False}


@router.post("/providers/{provider}/test")
def test_provider(provider: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Cheap connectivity probe. Video providers validate the stored key and
    report readiness — a real test generation happens on the next render."""
    import time

    key = _key_for(user, provider, db)
    if not key:
        raise HTTPException(status_code=400, detail="No key configured for this provider.")
    t0 = time.time()
    try:
        if provider == "openai":
            import httpx

            with httpx.Client(timeout=20.0) as client:
                r = client.get(f"{app_settings.OPENAI_BASE_URL}/models", headers={"Authorization": f"Bearer {key}"})
                if r.status_code != 200:
                    return {"ok": False, "provider": provider, "detail": f"HTTP {r.status_code} — check the key", "latency_ms": int((time.time() - t0) * 1000)}
                return {"ok": True, "provider": provider, "detail": "Models endpoint reachable", "latency_ms": int((time.time() - t0) * 1000)}
        if provider == "elevenlabs":
            import httpx

            with httpx.Client(timeout=20.0) as client:
                r = client.get("https://api.elevenlabs.io/v1/user", headers={"xi-api-key": key})
                if r.status_code != 200:
                    return {"ok": False, "provider": provider, "detail": f"HTTP {r.status_code} — check the key", "latency_ms": int((time.time() - t0) * 1000)}
                return {"ok": True, "provider": provider, "detail": "Account reachable", "latency_ms": int((time.time() - t0) * 1000)}
        # video providers: validate shape, full test on first render
        ok = key.startswith(("AIza", "sk-", "sk_", "kling", "Bearer ")) or len(key) >= 24
        return {
            "ok": ok,
            "provider": provider,
            "detail": "Key stored — live generation is exercised on the next render job." if ok else "Key format looks unusual",
            "latency_ms": int((time.time() - t0) * 1000),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "provider": provider, "detail": str(exc)[:200], "latency_ms": int((time.time() - t0) * 1000)}


@router.get("/audio")
def audio_defaults(user: User = Depends(get_current_user)):
    merged = {**app_settings.AUDIO_DEFAULTS, **(user.settings or {}).get("audio", {})}
    return {"audio": merged, "voices": VOICE_CATALOG}


@router.put("/audio")
def save_audio_defaults(body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    settings_dict = dict(user.settings or {})
    settings_dict["audio"] = {**app_settings.AUDIO_DEFAULTS, **(body or {})}
    user.settings = settings_dict
    db.commit()
    return {"audio": settings_dict["audio"]}
