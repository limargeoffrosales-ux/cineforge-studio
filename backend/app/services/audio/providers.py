"""TTS / narration provider adapters.

OpenAI TTS and ElevenLabs are supported live (keys via env or the in-app
provider settings). Microsoft Edge neural voices (`edge-tts`) need **no key
at all** and are the default — so narration always renders, even offline of
any paid provider. Without any network access the narration layer is skipped
and the soundtrack still renders music/SFX/ambience.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import numpy as np

from ...config import settings

log = logging.getLogger("cineforge.audio.providers")

VOICE_CATALOG = {
    "edge": {
        "id": "edge",
        "name": "Microsoft Edge (free — no key)",
        "model": "azure-neural",
        "voices": [
            {"id": "en-US-AriaNeural", "tone": "bright narrator", "genders": "f"},
            {"id": "en-US-JennyNeural", "tone": "soft, friendly", "genders": "f"},
            {"id": "en-US-ChristopherNeural", "tone": "deep documentary", "genders": "m"},
            {"id": "en-US-GuyNeural", "tone": "warm, charming", "genders": "m"},
            {"id": "en-GB-SoniaNeural", "tone": "expressive, British", "genders": "f"},
            {"id": "en-GB-RyanNeural", "tone": "authoritative, British", "genders": "m"},
            {"id": "en-AU-WilliamNeural", "tone": "easy-going", "genders": "m"},
            {"id": "en-IN-NeerjaNeural", "tone": "bright, melodic", "genders": "f"},
        ],
    },
    "openai": {
        "id": "openai",
        "name": "OpenAI TTS",
        "model": "tts-1-hd",
        "voices": [
            {"id": "alloy", "tone": "balanced", "genders": "neutral"},
            {"id": "echo", "tone": "warm, soft", "genders": "neutral"},
            {"id": "fable", "tone": "expressive, British", "genders": "neutral"},
            {"id": "onyx", "tone": "deep, authoritative", "genders": "m"},
            {"id": "nova", "tone": "bright, friendly", "genders": "f"},
            {"id": "shimmer", "tone": "clear, uplifting", "genders": "f"},
        ],
    },
    "elevenlabs": {
        "id": "elevenlabs",
        "name": "ElevenLabs",
        "model": "eleven_multilingual_v2",
        "voices": [
            {"id": "21m00Tcm4TlvDq8ikWAM", "tone": "warm narrator", "genders": "m"},
            {"id": "EXAVITQu4vr4xnSDxMaL", "tone": "bright presenter", "genders": "f"},
            {"id": "pNInz6obpgDQGcFmaJgB", "tone": "deep documentary", "genders": "m"},
        ],
    },
}

OPENAI_DEFAULT_VOICE = settings.OPENAI_AUDIO_VOICE if hasattr(settings, "OPENAI_AUDIO_VOICE") else "nova"

# pipeline character voice styles → closest free Edge neural voice
_EDGE_STYLE_MAP = {
    "nova": "en-US-AriaNeural",
    "shimmer": "en-US-JennyNeural",
    "echo": "en-US-GuyNeural",
    "alloy": "en-US-GuyNeural",
    "onyx": "en-US-ChristopherNeural",
    "fable": "en-GB-SoniaNeural",
    "conversational": "en-US-GuyNeural",
    "documentary": "en-US-ChristopherNeural",
}
_EDGE_DEFAULT = "en-US-AriaNeural"


def edge_voice(style: str) -> str:
    """Map a pipeline voice style onto a free Edge neural voice id."""
    if style in _EDGE_STYLE_MAP:
        return _EDGE_STYLE_MAP[style]
    if style in {v["id"] for v in VOICE_CATALOG["edge"]["voices"]}:
        return style
    return _EDGE_DEFAULT


def _ffmpeg() -> str:
    from imageio_ffmpeg import get_ffmpeg_exe

    return get_ffmpeg_exe()


def decode_mp3_to_wav(path: Path) -> np.ndarray:
    """Decode an mp3 to a mono float32 array at 44.1k."""
    raw = subprocess.run(
        [_ffmpeg(), "-y", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", "44100", "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32)


def _tts_key(provider: str, owner_id: str | None = None) -> str | None:
    """User-stored (encrypted DB) key first, env fallback. None for keyless providers."""
    if provider == "edge":
        return "free"
    if owner_id:
        try:
            from sqlalchemy import select

            from ...db import SessionLocal
            from ...models import ProviderKey
            from ...services.vault import decrypt_secret

            db = SessionLocal()
            try:
                row = db.scalar(select(ProviderKey).where(ProviderKey.user_id == owner_id, ProviderKey.provider == provider))
                if row and row.encrypted_key:
                    try:
                        return decrypt_secret(row.encrypted_key)
                    except Exception:  # noqa: BLE001
                        pass
            finally:
                db.close()
        except Exception:  # noqa: BLE001
            pass
    return getattr(settings, "OPENAI_API_KEY" if provider == "openai" else "ELEVENLABS_API_KEY", "") or None


def synthesize(text: str, voice: str, provider: str = "openai", owner_id: str | None = None) -> dict | None:
    """Returns {audio, duration_s} or None if every provider is unavailable.

    Keyless by default: any provider without a configured key falls back to
    the free Microsoft Edge neural voices; only a full network failure returns
    None (narration skipped, soundtrack still renders).
    """
    if provider == "edge":
        return _edge_tts(text, edge_voice(voice))
    key = _tts_key(provider, owner_id)
    if provider == "openai" and key:
        return _openai_tts(text, voice or OPENAI_DEFAULT_VOICE, key)
    if provider == "elevenlabs" and key:
        return _elevenlabs_tts(text, voice, key)
    log.info("no key for %s — falling back to free Edge neural TTS", provider)
    return _edge_tts(text, edge_voice(voice))


def _edge_tts(text: str, voice: str) -> dict | None:
    """Free Microsoft Edge neural TTS — no API key required."""
    try:
        from edge_tts import Communicate

        from ..video.local import ensure_media_dir

        tmp = ensure_media_dir() / "audio" / "tts"
        tmp.mkdir(parents=True, exist_ok=True)
        path = tmp / f"edge-{abs(hash(text)) % 10**8}-{voice}.mp3"
        if not path.exists():
            import asyncio

            asyncio.run(Communicate(text[:4000], voice, rate="+0%", volume="+0%").save(str(path)))
        audio = decode_mp3_to_wav(path)
        if len(audio) < 100:
            path.unlink(missing_ok=True)
            raise ValueError("decoded clip too short")
        return {"audio": audio, "duration_s": round(len(audio) / 44100, 2), "provider": "edge", "voice": voice}
    except Exception as exc:  # noqa: BLE001
        log.warning("Edge TTS failed (%s) — narration skipped", exc)
        return None


def _openai_tts(text: str, voice: str, key: str) -> dict | None:
    import httpx

    try:
        with httpx.Client(timeout=90.0) as client:
            resp = client.post(
                f"{settings.OPENAI_BASE_URL}/audio/speech",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": "tts-1-hd", "voice": voice, "input": text[:4000], "response_format": "mp3"},
            )
            resp.raise_for_status()
        from ..video.local import ensure_media_dir

        tmp = ensure_media_dir() / "audio" / "tts"
        tmp.mkdir(parents=True, exist_ok=True)
        path = tmp / f"tts-{abs(hash(text)) % 10**8}.mp3"
        path.write_bytes(resp.content)
        audio = decode_mp3_to_wav(path)
        return {"audio": audio, "duration_s": round(len(audio) / 44100, 2), "provider": "openai", "voice": voice}
    except Exception as exc:  # noqa: BLE001
        log.warning("OpenAI TTS failed: %s", exc)
        return None


def _elevenlabs_tts(text: str, voice: str, key: str) -> dict | None:
    import httpx

    try:
        with httpx.Client(timeout=90.0) as client:
            resp = client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
                headers={"xi-api-key": key, "Content-Type": "application/json"},
                json={"text": text[:4000], "model_id": "eleven_multilingual_v2", "voice_settings": {"stability": 0.55, "similarity_boost": 0.8}},
            )
            resp.raise_for_status()
        from ..video.local import ensure_media_dir

        tmp = ensure_media_dir() / "audio" / "tts"
        tmp.mkdir(parents=True, exist_ok=True)
        path = tmp / f"el-{abs(hash(text)) % 10**8}.mp3"
        path.write_bytes(resp.content)
        audio = decode_mp3_to_wav(path)
        return {"audio": audio, "duration_s": round(len(audio) / 44100, 2), "provider": "elevenlabs", "voice": voice}
    except Exception as exc:  # noqa: BLE001
        log.warning("ElevenLabs TTS failed: %s", exc)
        return None
