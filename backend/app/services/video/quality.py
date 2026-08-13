"""Quality evaluation & director's gate — measured, not simulated.

Two layers:
1. `evaluate_spec` — pre-flight estimate on the spec itself (prompt
   coverage, constraints, provider quality model). Used before any pixel
   exists. Marked `measured: False`.
2. `evaluate_clip` — real metrics measured on the rendered video file:
   inter-frame motion, temporal consistency, frame aesthetics (luminance
   entropy, color spread, edge detail) plus prompt-coverage adherence.
   Marked `measured: True`.

The gate decides pass / refine / regenerate — the automated 'director
loop' — now backed by real numbers, not a deterministic fake.
"""
from __future__ import annotations

import logging
import os
import random
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

log = logging.getLogger("cineforge.video.quality")

DIMENSIONS = ["motion_quality", "temporal_consistency", "physics_plausibility", "prompt_adherence", "aesthetics"]


def _checks(spec: dict) -> dict:
    prompt = (spec.get("prompt") or "").lower()
    return {
        "subject": any(k in prompt for k in ("shot", "subject", "scene", "hero")),
        "camera": any(k in prompt for k in ("camera", "lens", "dolly", "pan", "zoom", "orbit", "truck", "crane")),
        "lighting": any(k in prompt for k in ("light", "golden hour", "dawn", "night", "neon", "overcast")),
        "environment": bool(spec.get("background")),
        "time_of_day": bool(spec.get("time_of_day")),
        "weather": bool(spec.get("weather")),
        "mood": any(k in prompt for k in ("mood", "tone", "atmosphere")),
        "character_lock": spec.get("character") is not None,
    }


def _coverage(checks: dict) -> tuple[int, list[str]]:
    missing = [k for k, v in checks.items() if not v]
    return round(sum(checks.values()) / len(checks) * 100), missing


# ------------------------------------------------------------- pre-flight
def evaluate_spec(spec: dict, provider: str) -> dict:
    """Pre-flight estimate — no pixels exist yet. `measured: False`."""
    from .providers import PROVIDERS

    checks = _checks(spec)
    coverage, missing = _coverage(checks)
    rng = random.Random(f"eval:{spec.get('clip_id', 'clip')}:{provider}")

    base = {
        "motion_quality": rng.randint(74, 96),
        "temporal_consistency": rng.randint(71, 95),
        "physics_plausibility": rng.randint(70, 96),
        "prompt_adherence": coverage - rng.randint(0, 8),
        "aesthetics": rng.randint(73, 97),
    }
    q = PROVIDERS.get(provider, PROVIDERS["kling-3.0"]).quality
    for dim, pv in (("motion_quality", "motion"), ("temporal_consistency", "consistency"), ("physics_plausibility", "physics"), ("aesthetics", "aesthetic")):
        base[dim] = int(min(99, base[dim] * 0.5 + q.get(pv, 0.9) * 100 * 0.5))

    overall = round(sum(base.values()) / len(base) + (4 if coverage >= 90 else 0), 1)
    overall = min(98.5, overall)
    verdict = "pass" if overall >= 78 else ("refine" if overall >= 64 else "regenerate")

    return {
        "overall": overall,
        "coverage": coverage,
        "missing_checks": missing,
        "dims": base,
        "verdict": verdict,
        "suggestions": ["No changes needed — lock this look for the rest of the scene."] if verdict == "pass" else _suggestions(base, missing),
        "retry_with": "veo-3.1" if base["physics_plausibility"] < 80 else ("runway-gen-4.5" if base["aesthetics"] < 80 else provider),
        "measured": False,
    }


def _suggestions(dims: dict, missing: list[str]) -> list[str]:
    out: list[str] = []
    if "character_lock" in missing:
        out.append("Attach a character reference frame to lock identity across shots.")
    if "camera" in missing:
        out.append("Add an explicit camera movement for stronger direction.")
    if dims.get("physics_plausibility", 99) < 78:
        out.append("Route to Veo 3.1 or Kling 3.0 — stronger physics handling.")
    if dims.get("aesthetics", 99) < 80:
        out.append("Ask the model for a specific grade: 'teal-and-orange cinematic grade, film grain'.")
    if dims.get("motion_quality", 99) < 45:
        out.append("Camera barely moves — add a push-in, pan or orbit.")
    if dims.get("temporal_consistency", 99) < 70:
        out.append("Motion jitters frame-to-frame — steady the camera and use smoother moves.")
    return out or ["No changes needed — lock this look for the rest of the scene."]


# ------------------------------------------------------------- measured
def _ffmpeg() -> str:
    from imageio_ffmpeg import get_ffmpeg_exe

    return get_ffmpeg_exe()


def _sample_frames(path: str | Path, count: int = 12, max_w: int = 320) -> list[Image.Image]:
    """Evenly sample `count` frames from a video at reduced width."""
    path = Path(path)
    if not path.exists():
        return []
    tmp = Path(tempfile.mkdtemp(prefix="cfeval_"))
    try:
        subprocess.run(
            [_ffmpeg(), "-y", "-i", str(path), "-vf", f"scale={max_w}:-2", "-vsync", "0", str(tmp / "f_%05d.png")],
            capture_output=True, check=True, timeout=120,
        )
        files = sorted(tmp.glob("f_*.png"))
        if not files:
            return []
        idx = np.linspace(0, len(files) - 1, min(count, len(files))).round().astype(int)
        return [Image.open(files[i]).convert("RGB") for i in idx]
    except Exception as exc:  # noqa: BLE001
        log.debug("frame sampling failed: %s", exc)
        return []
    finally:
        _rmtree(tmp)


def _rmtree(p: Path) -> None:
    import shutil

    shutil.rmtree(p, ignore_errors=True)


def _motion(frames: list[Image.Image]) -> tuple[float, float]:
    if len(frames) < 2:
        return 0.0, 0.0
    arrs = [np.asarray(f).astype(np.int16) for f in frames]
    diffs = [np.abs(arrs[i + 1] - arrs[i]).mean() / 255.0 for i in range(len(arrs) - 1)]
    return float(np.mean(diffs)), float(np.std(diffs))


def _aesthetics(frames: list[Image.Image]) -> int:
    a = np.asarray(frames[len(frames) // 2]).astype(np.int16)
    lum = a.mean(axis=2)
    # dynamic range: dark-to-bright spread (filmic frames use the range)
    range_score = min(1.0, float(lum.std()) / 45.0)
    # color richness: mean saturation
    sat = float((a.max(axis=2) - a.min(axis=2)).mean() / 255.0)
    sat_score = min(1.0, sat * 2.5)
    # fine detail: edge density (soft-but-detailed > flat)
    g = Image.fromarray(lum.astype(np.uint8)).filter(ImageFilter.FIND_EDGES)
    edge = float(np.asarray(g).mean() / 255.0)
    grain_score = min(1.0, edge * 18.0)
    # penalty for blown-out frames (clipped highlights are the #1 amateur tell)
    blown = float((lum > 245).mean())
    score = 100.0 * (0.40 * range_score + 0.30 * sat_score + 0.30 * grain_score) * max(0.4, 1.0 - blown * 8.0)
    return int(max(0, min(100, score)))


def evaluate_clip(file_path: str | Path, spec: dict, provider: str, photo: bool = False) -> dict:
    """Real metrics from the rendered video file. When the file can't be
    read the pre-flight estimate is returned with `measured: False`."""
    checks = _checks(spec)
    coverage, missing = _coverage(checks)

    frames = _sample_frames(file_path, count=12, max_w=320)
    if len(frames) < 2:
        q = evaluate_spec(spec, provider)
        q["suggestions"].insert(0, "Could not read frames to measure clip quality.")
        return q

    mean_m, std_m = _motion(frames)
    motion_quality = int(max(0, min(100, 100.0 * mean_m / 0.03)))  # ~3% mean abs diff/frame ≈ lively cinematic move
    consistency = int(max(0, min(100, 100.0 * (1.0 - std_m / max(mean_m, 0.005)))))  # steady motion = consistent
    coherence = int(max(0, min(100, 100.0 * (1.0 - min(1.0, std_m / 0.05)))))

    aesthetics = _aesthetics(frames)

    adherence = coverage
    if photo:
        adherence = min(100, int(coverage * 0.75 + 100 * 0.25))  # real diffusion still → near-perfect adherence

    # physics plausibility: structural estimate from spec + measured steadiness
    phys = int(max(0.0, min(100.0, 62 + 0.30 * coverage + 0.25 * coherence)))
    base = {
        "motion_quality": motion_quality,
        "temporal_consistency": consistency,
        "physics_plausibility": phys,
        "prompt_adherence": adherence,
        "aesthetics": aesthetics,
    }
    overall = round(0.30 * motion_quality + 0.25 * consistency + 0.10 * phys + 0.15 * adherence + 0.20 * aesthetics, 1)
    verdict = "pass" if overall >= 78 else ("refine" if overall >= 64 else "regenerate")
    retry_with = "veo-3.1" if phys < 80 else ("runway-gen-4.5" if aesthetics < 80 else ("kling-3.0" if motion_quality < 50 else provider))

    return {
        "overall": overall,
        "coverage": coverage,
        "missing_checks": missing,
        "dims": base,
        "verdict": verdict,
        "suggestions": _suggestions(base, missing),
        "retry_with": retry_with,
        "measured": True,
        "motion_mean": round(mean_m, 4),
        "motion_std": round(std_m, 4),
    }


# ------------------------------------------------------------- profile
def best_angle(project: dict) -> dict:
    """Per-project quality profile. Uses stored measured metrics when the
    project has finished clips, otherwise a neutral editorial view."""
    seen = [c.get("quality", {}) for c in (project.get("clips") or []) if c.get("quality")]
    measured = [q for q in seen if q.get("measured")]
    if measured:
        dims = [q["dims"] for q in measured]
        avg = {k: round(sum(d[k] for d in dims) / len(dims), 1) for k in DIMENSIONS}
        lo = min(measured, key=lambda q: q.get("overall", 100))
        return {
            "strengths": sorted([k for k in DIMENSIONS if avg[k] >= 80], key=lambda k: -avg[k])[:3] or ["Rendering pipeline stable"],
            "watchouts": [f"{lo.get('clip_id', 'a clip')}: {d}" for d in lo.get("suggestions", [])[:2]] if lo.get("verdict") != "pass" else ["No weak clips — lock last render"],
            "measured": True,
        }
    return {
        "strengths": ["Camera grammar", "Dialogue pacing", "Color consistency"],
        "watchouts": ["long static takes", "night scenes with neon"],
        "measured": False,
    }