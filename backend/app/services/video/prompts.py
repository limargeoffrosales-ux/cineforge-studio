"""Director-grade prompt compiler.

Turns the shot plan + storyboard + script into model-native prompt payloads.
This is a core differentiator: raw users type "a beach", CineForge compiles
full cinematography grammar — shot type, lens, movement, lighting, mood,
environment, time of day, weather, character locks — and formats it per
provider (Veo wants flowing language, Kling wants explicit fields, etc.).
"""
from __future__ import annotations

import hashlib
import random

MOVEMENT_VERBS = {
    "dolly in": "a slow dolly-in", "dolly out": "a slow dolly-out", "push in": "a deliberate push-in",
    "pull out": "a slow pull-out", "orbit": "an orbital shot circling the subject",
    "pan": "a smooth pan", "whip pan": "a fast whip-pan", "tilt": "a slow tilt",
    "zoom": "a slow zoom", "rack focus": "a rack focus", "truck": "a lateral truck",
    "crane": "a crane rise", "static": "a locked-off static shot",
}

CAMERA_NOUNS = {
    "drone": "aerial drone", "crane": "crane", "handheld": "handheld", "steadicam": "steadicam",
    "gimbal": "gimbal-stabilized", "slider": "slider", "fpv": "FPV", "orbit": "orbit",
    "underwater": "underwater housing", "macro": "macro", "": "camera",
}

MOOD_TEXT = {
    "mysterious": "moody, mysterious atmosphere", "uplifting": "uplifting, hopeful tone",
    "tense": "building tension", "warm": "warm, intimate feel", "epic": "epic scale and grandeur",
    "intimate": "intimate, close energy",
}

LIGHT_TEXT = {
    "golden hour": "golden hour light", "dawn": "soft dawn light", "night": "night, moonlight and practicals",
    "overcast": "soft overcast light", "neon": "neon glow", "moody": "low-key dramatic lighting",
    "diffused": "diffused window light", "sunset": "warm sunset backlight", "midday": "harsh midday sun",
}

NEGATIVE_BASE = [
    "blurry", "low quality", "jittery motion", "morphing faces", "text artifacts",
    "watermark", "extra limbs", "flickering", "distorted geometry",
]


def build_spec(shot: dict, scene: dict, project: dict, decision: dict, index: int, fps: int = 30) -> dict:
    """Assemble the full generation spec for one clip."""
    palette = project.get("environments") or []
    env = palette[(int(scene.get("id", "scene-0").split("-")[-1] or 0) - 1) % max(1, len(palette))] if palette else {}
    rng = random.Random(f"spec:{project.get('id')}:{shot.get('id')}")
    aspect = aspect_for(project.get("category", "youtube"))
    w, h = (1920, 1080) if aspect == "16:9" else (1080, 1920)
    duration = float(shot.get("duration") or scene.get("duration") or 5.0)
    provider = decision["chosen"]
    prompt = compile_prompt(shot, scene, env, project, provider)
    return {
        "clip_id": f"{shot.get('id', 'clip')}-{index}",
        "scene_id": scene.get("id", "scene-1"),
        "scene_title": scene.get("title", ""),
        "shot": shot,
        "provider": provider,
        "prompt": prompt,
        "negative_prompt": " , ".join(NEGATIVE_BASE),
        "width": w, "height": h, "fps": fps, "duration_s": duration,
        "aspect_ratio": aspect,
        "seed": rng.randint(1, 999999),
        "movement": shot.get("movement", "static"),
        "composition": shot.get("shot_type", "Medium"),
        "camera": shot.get("camera_type", ""),
        "lighting": (shot.get("lighting") or scene.get("lighting") or "soft").lower(),
        "mood": (shot.get("mood") or scene.get("mood") or "neutral").lower(),
        "time_of_day": shot.get("time_of_day", "midday"),
        "weather": shot.get("weather", "clear"),
        "background": shot.get("background") or env.get("name", "Studio Set"),
        "environment_category": env.get("category", "generic"),
        "palette": env.get("palette", ["#2b2b33", "#4a4a55", "#f5b301"]),
        "character": _character_for(shot, project),
        "first_frame": None,  # set when a storyboard frame / face ref is provided
        "last_frame": None,
        "notes": "; ".join(decision.get("reasons", [])),
    }


def _character_for(shot: dict, project: dict) -> dict | None:
    chars = project.get("characters") or []
    if not chars:
        return None
    c = chars[0]
    return {
        "name": c.get("name", "Narrator"),
        "palette": c.get("palette", ["#f5b301", "#222", "#fff"]),
        "position": "center",
        "action": shot.get("character_action", "addressing camera"),
    }


def aspect_for(category: str) -> str:
    if category in ("tiktok", "instagram", "reels", "shorts"):
        return "9:16"
    return "16:9"


def compile_prompt(shot: dict, scene: dict, env: dict, project: dict, provider: str) -> str:
    """Provider-aware cinematic prompt. Providers are mostly prompt-compatible;
    Kling additionally receives explicit camera fields (see kling adapter)."""
    subject = _subject_text(shot, project)
    movement = MOVEMENT_VERBS.get((shot.get("movement") or "static").lower(), "a smooth cinematic move")
    camera = CAMERA_NOUNS.get((shot.get("camera_type") or "").lower(), "camera")
    lens = shot.get("lens", "35mm")
    light = LIGHT_TEXT.get((shot.get("lighting") or "soft").lower(), f"{shot.get('lighting')} lighting")
    mood = MOOD_TEXT.get((shot.get("mood") or "neutral").lower(), f"{shot.get('mood')} mood")
    env_name = shot.get("background") or env.get("name", "a cinematic location")
    tod = shot.get("time_of_day", "midday")
    weather = shot.get("weather", "clear")
    shot_type = shot.get("shot_type", "Medium")
    framing = shot.get("framing", "medium")
    p = (
        f"{shot_type} shot, {framing} framing: {subject}, with {movement} from a {camera} on a {lens} lens, "
        f"set in {env_name}, {tod}, {weather} sky, lit by {light}. {mood.capitalize()}. "
        f"Photoreal, cinematic color grade, 24fps filmic look, shallow depth of field where appropriate, "
        f"natural motion with realistic physics."
    )
    # provider tailoring
    if provider == "runway-gen-4.5":
        p += " Editorial, stylized but grounded; consistent subject identity across frames."
    elif provider == "kling-3.0":
        p += " Smooth human motion; explicit camera move; coherent environment."
    elif provider == "seedance-2.0":
        p += " Continuous multi-shot coherence; stable subjects; clean rendering."
    elif provider == "veo-3.1":
        p += " Physically plausible interactions; consistent lighting across the take; ambient audio-friendly scene."
    return p


def _subject_text(shot: dict, project: dict) -> str:
    chars = project.get("characters") or []
    if chars and (shot.get("character_action") or "delivers line" in str(shot.get("character_action"))):
        c = chars[0]
        action = shot.get("character_action", "addressing the camera")
        return f"{c.get('name', 'a presenter')} {action}"
    if shot.get("props") and shot.get("props") != "none":
        return f"a {shot['props']} as the hero object"
    return "the scene's main subject"


def spec_seed(spec: dict) -> str:
    return hashlib.sha256(spec.get("clip_id", "clip").encode()).hexdigest()
