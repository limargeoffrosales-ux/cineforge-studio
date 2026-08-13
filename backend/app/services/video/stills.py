"""Keyless photoreal still rail.

Fetches real diffusion stills from the free Pollinations image endpoint
(image.pollinations.ai — no API key required) and turns them into the
background planes of the 2.5D engine, so every render has photoreal
backdrops even with zero cloud keys. Falls back to painted planes when
offline / unreachable, and caches every still on disk so re-renders are
instant and deterministic (same prompt+seed = same image).

Env switches:
  CINEFORGE_STILLS     "off" / "0"  → force painted planes
  CINEFORGE_STILLS_MODEL  flux | turbo (default flux)
  CINEFORGE_STILLS_TIMEOUT  seconds per request (default 30)
"""
from __future__ import annotations

import hashlib
import io
import logging
import os
import random
import urllib.parse
from pathlib import Path

import httpx
from PIL import Image

log = logging.getLogger("cineforge.video.stills")

BASE = "https://image.pollinations.ai/prompt/"
REFERRER = os.getenv("CINEFORGE_REFERRER", "https://cineforge.studio")

_probe_state = {"probed": False, "ok": None}


def enabled() -> bool:
    v = os.getenv("CINEFORGE_STILLS", "").strip().lower()
    return v not in ("off", "0", "false", "no")


def stills_dir() -> Path:
    p = os.getenv("CINEFORGE_STILLS_DIR")
    root = Path(p) if p else Path(os.getenv("MEDIA_DIR", "./media")).resolve() / "stills"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _probe() -> bool:
    """One tiny request per process to learn if the free rail is reachable."""
    if not enabled():
        return False
    if _probe_state["probed"]:
        return bool(_probe_state["ok"])
    _probe_state["probed"] = True
    try:
        with httpx.Client(timeout=4, follow_redirects=True) as c:
            r = c.get(BASE + "test", params={"width": 8, "height": 8, "nologo": "true", "seed": 1})
        _probe_state["ok"] = r.status_code == 200 and len(r.content) > 0
    except Exception:  # noqa: BLE001
        _probe_state["ok"] = False
    log.info("stills rail reachable: %s", _probe_state["ok"])
    return bool(_probe_state["ok"])


def _cache_key(prompt: str, seed: int, width: int, height: int, model: str) -> Path:
    h = hashlib.sha1(f"{prompt}|{seed}|{width}x{height}|{model}".encode("utf-8")).hexdigest()[:20]
    return stills_dir() / f"{h}.jpg"


def get_still_prompt(spec: dict) -> str:
    """Structured, None-safe prompt for the photoreal still — derived from
    the spec's own fields instead of the LLM prompt template (which can
    contain literal 'None' fragments when fields are unset)."""
    clean = lambda v: str(v or "").strip().strip('"').lower()  # noqa: E731
    def take(v: str) -> str:
        return "" if clean(v) in ("", "none", "auto", "unspecified") else clean(v)

    st = take(spec.get("shot_type")) or take(spec.get("framing")) or "cinematic shot"
    bg = take(spec.get("background")) or take(spec.get("scene_title")) or take(spec.get("environment_category"))
    tod = take(spec.get("time_of_day"))
    weather = take(spec.get("weather"))
    lighting = take(spec.get("lighting"))
    mood = take(spec.get("mood"))
    style = take(spec.get("style")) or "photoreal"
    parts = [f"{st} of {bg}" if bg else st]
    if tod:
        parts.append(tod)
    if weather:
        parts.append(weather)
    if lighting:
        parts.append(f"{lighting} lighting")
    if mood:
        parts.append(f"{mood} mood")
    parts.append(f"{style}, cinematic color grade, filmic look, shallow depth of field where appropriate, high detail")
    return ", ".join(parts)[:400]


def fetch_still(
    prompt: str,
    seed: int | None = None,
    width: int = 1024,
    height: int = 576,
    model: str | None = None,
) -> Image.Image | None:
    """Fetch a photoreal still for a scene prompt. Returns None when the free
    rail is disabled, unreachable or fails — callers must keep their painted
    fallback."""
    if not enabled():
        return None
    model = model or os.getenv("CINEFORGE_STILLS_MODEL", "flux")
    p = (prompt or "").strip()[:400]
    if not p:
        return None
    seed = seed if seed is not None else random.Random(p).randint(1, 999_999)
    key = _cache_key(p, seed, width, height, model)
    if key.exists():
        try:
            return Image.open(key).convert("RGB")
        except Exception:  # noqa: BLE001
            key.unlink(missing_ok=True)
    if not _probe():
        return None

    url = f"{BASE}{urllib.parse.quote(p, safe='')}"
    params = {
        "width": width, "height": height, "seed": seed,
        "nologo": "true", "model": model, "enhance": "true",
        "safe": "true", "referrer": REFERRER,
    }
    timeout = float(os.getenv("CINEFORGE_STILLS_TIMEOUT", "30"))
    last_err: Exception | None = None
    for attempt in range(2):
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as c:
                r = c.get(url, params=params)
            if r.status_code == 200 and r.content:
                img = Image.open(io.BytesIO(r.content)).convert("RGB")
                img.save(key, quality=88)
                log.info("still fetched (%s) %sx%s seed=%s", model, width, height, seed)
                return img
            last_err = RuntimeError(f"status {r.status_code}")
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            log.warning("still fetch attempt %d/%d failed: %s", attempt + 1, 2, exc)
    log.info("still fetch failed (%s) — falling back to painted planes", last_err)
    return None
