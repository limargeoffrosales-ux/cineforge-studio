"""Quality evaluation & director's gate.

Two layers:
1. Deterministic checks on the spec itself (prompt coverage, constraints).
2. Simulated multimodal evaluation (motion quality, temporal consistency,
   physics plausibility, prompt adherence, aesthetics) seeded deterministically
   per clip — standing in for a real VLM/scorer (CLIP + motion metrics) which
   plugs in at Phase 3.

The gate decides pass / refine / regenerate and recommends which provider to
retry on — the automated 'director loop'.
"""
from __future__ import annotations

import random
from typing import Any

DIMENSIONS = ["motion_quality", "temporal_consistency", "physics_plausibility", "prompt_adherence", "aesthetics"]


def evaluate_spec(spec: dict, provider: str) -> dict:
    rng = random.Random(f"eval:{spec.get('clip_id', 'clip')}:{provider}")

    # ---- deterministic checks ----
    prompt = spec.get("prompt", "")
    checks = {
        "subject": any(k in prompt.lower() for k in ("shot", "subject", "scene", "hero")),
        "camera": any(k in prompt.lower() for k in ("camera", "lens", "dolly", "pan", "zoom", "orbit", "truck", "crane")),
        "lighting": any(k in prompt.lower() for k in ("light", "golden hour", "dawn", "night", "neon", "overcast")),
        "environment": bool(spec.get("background")),
        "time_of_day": bool(spec.get("time_of_day")),
        "weather": bool(spec.get("weather")),
        "mood": any(k in prompt.lower() for k in ("mood", "tone", "atmosphere")),
        "character_lock": spec.get("character") is not None,
    }
    coverage = round(sum(checks.values()) / len(checks) * 100)
    missing = [k for k, v in checks.items() if not v]

    # ---- simulated VLM dimensions (deterministic per clip+provider) ----
    base = {
        "motion_quality": rng.randint(74, 96),
        "temporal_consistency": rng.randint(71, 95),
        "physics_plausibility": rng.randint(70, 96),
        "prompt_adherence": coverage - rng.randint(0, 8),
        "aesthetics": rng.randint(73, 97),
    }
    # provider bias from its quality model
    from .providers import PROVIDERS

    q = PROVIDERS.get(provider, PROVIDERS["kling-3.0"]).quality
    for dim, pv in (("motion_quality", "motion"), ("temporal_consistency", "consistency"), ("physics_plausibility", "physics"), ("aesthetics", "aesthetic")):
        base[dim] = int(min(99, base[dim] * 0.5 + q.get(pv, 0.9) * 100 * 0.5))

    overall = round(sum(base.values()) / len(base) + (4 if coverage >= 90 else 0), 1)
    overall = min(98.5, overall)

    verdict = "pass" if overall >= 78 else ("refine" if overall >= 64 else "regenerate")
    suggestions: list[str] = []
    if "character_lock" in missing:
        suggestions.append("Attach a character reference frame to lock identity across shots.")
    if "camera" in checks and not checks["camera"]:
        suggestions.append("Add an explicit camera movement for stronger direction.")
    if base["temporal_consistency"] < 80:
        suggestions.append("Reuse the previous clip's last frame as the next clip's first frame (scene extension).")
    if base["physics_plausibility"] < 78:
        suggestions.append("Route to Veo 3.1 or Kling 3.0 — stronger physics handling.")
    if base["aesthetics"] < 80:
        suggestions.append("Ask the model for a specific grade: 'teal-and-orange cinematic grade, film grain'.")
    if not suggestions:
        suggestions.append("No changes needed — lock this look for the rest of the scene.")

    retry_with = "veo-3.1" if base["physics_plausibility"] < 80 else ("runway-gen-4.5" if base["aesthetics"] < 80 else provider)

    return {
        "overall": overall,
        "coverage": coverage,
        "missing_checks": missing,
        "dims": base,
        "verdict": verdict,
        "suggestions": suggestions,
        "retry_with": retry_with,
    }


def best_angle(project: dict) -> dict:
    """Per-project quality profile shown in the Video Lab."""
    rng = random.Random(f"profile:{project.get('id', 'x')}")
    return {
        "strengths": [k for k, v in sorted({"Dialogue pacing": 9, "Visual continuity": rng.randint(7, 9), "Camera grammar": 9, "Color consistency": rng.randint(7, 9)}.items(), key=lambda kv: -kv[1])[:3]],
        "watchouts": rng.sample(["long static takes", "night scenes with neon", "fast whip-pans", "crowd shots"], 2),
    }
