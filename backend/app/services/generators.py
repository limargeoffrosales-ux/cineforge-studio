"""Procedural AI content generators.

Every stage has two paths: a real-model path (OpenAI-compatible API via
services/llm.py) and a deterministic procedural path that produces rich,
plausible production assets offline. The procedural path is seeded by the
project so the same project always regenerates the same output (stable
characters, consistent storyboards), while the LLM path raises quality.
"""
import hashlib
import random
from typing import Any

# ------------------------------------------------------------------ helpers
def rng(seed: str) -> random.Random:
    return random.Random(int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16))


def pick(r: random.Random, items: list[str], n: int = 1) -> list[str]:
    return r.sample(items, min(n, len(items)))


# ------------------------------------------------------------ curated pools
HOOKS = [
    "Nobody talks about this side of {topic} — and it changes everything",
    "The truth about {topic} that took me years to understand",
    "I spent 30 days inside {topic} and here's what happened",
    "This is why {topic} is about to explode",
    "What they don't teach you about {topic}",
]

ANGLES = [
    "The hidden history behind {topic} and how it shaped today",
    "A first-person journey through {topic} with practical takeaways",
    "The economics and science of {topic}, explained simply",
    "Myths vs. reality: what experts get wrong about {topic}",
    "A cinematic before/after story of {topic} across generations",
]

AUDIENCE = [
    "Curious lifelong learners (25–45) who prefer story-first education",
    "Creators looking for authentic, visually rich storytelling",
    "Students and educators needing a memorable overview",
    "Professionals who want a sharp, no-fluff briefing",
]

FINDING_TEMPLATES = [
    ("Origin", "The earliest recorded roots of {topic} trace back further than most people assume, with primary sources indicating a formative period around the {era}."),
    ("Key Turning Point", "A decisive shift happened when {actor} pushed {topic} into the mainstream — a moment most summaries skip."),
    ("Current State", "Today, {topic} sits at an inflection point: adoption is accelerating while the fundamentals are still widely misunderstood."),
    ("Surprising Detail", "One of the least-known facts: behind the scenes, {detail}, which quietly explains most of what outsiders find confusing."),
    ("Why It Matters", "{topic} matters because it changes the default answer to an everyday question millions of people ask."),
]

TIMELINE_ERAS = ["early 2000s", "the 1960s", "the industrial era", "the digital decade", "the last five years"]
TIMELINE_ACTORS = ["pioneers", "a handful of researchers", "grassroots communities", "major platforms", "independent creators"]
TIMELINE_DETAILS = [
    "most of the visible progress relies on invisible infrastructure",
    "the terminology was coined almost by accident",
    "early adopters were dismissed before being proven right",
    "a single design decision shaped everything that followed",
    "the best results come from combining two older ideas",
]

SCRIPT_TEMPLATES = [
    {
        "title": "How {topic} Actually Works",
        "hook": "Stop scrolling for two minutes, because by the end of this video you will never see {topic} the same way again.",
        "acts": [
            ("The Hook", "Open with the surprising detail and the promise: a clear mental model by the end."),
            ("The Build", "Walk through the origin, the turning point, and the current state with vivid examples."),
            ("The Payoff", "Reveal the practical takeaway, address the biggest myth, and land the call to action."),
        ],
    },
    {
        "title": "{topic}: The Full Story",
        "hook": "Everyone has an opinion about {topic}. Almost no one knows the full story. That ends now.",
        "acts": [
            ("Setup", "Establish why {topic} deserves your attention and the question the video will answer."),
            ("Rising Action", "Three escalating chapters: the past, the present, and the forces shaping the future."),
            ("Resolution", "The single most useful insight, plus exactly what to do with it."),
        ],
    },
]

TONE_LINES = {
    "cinematic": "slow, measured, atmospheric; let images breathe",
    "energetic": "fast cuts, rising energy, short punchy sentences",
    "educational": "clear signposting, analogies, recap moments",
    "inspirational": "warm, uplifting, second-person direct address",
    "professional": "confident, precise, minimal rhetorical flourish",
    "humorous": "dry wit, playful asides, comedic timing",
}

# -------------------------------------------------------------- research
def generate_research(topic: str, language: str, seed: str) -> dict:
    r = rng(f"research:{seed}:{topic}")
    era = pick(r, TIMELINE_ERAS, 1)[0]
    actor = pick(r, TIMELINE_ACTORS, 1)[0]
    detail = pick(r, TIMELINE_DETAILS, 1)[0]
    findings = [
        {
            "title": t,
            "summary": s.format(topic=topic, era=era, actor=actor, detail=detail),
            "confidence": round(r.uniform(0.72, 0.96), 2),
            "sources": pick(r, ["primary archives", "industry reports", "academic papers", "expert interviews", "platform data"], 2),
        }
        for t, s in FINDING_TEMPLATES
    ]
    timeline = [
        {"year": y, "event": f"{a} bring {topic} into wider awareness"}
        for y, a in [("2016", "early experiments"), ("2019", "platforms and studios"), ("2022", "mainstream adoption"), ("2024", "regulatory attention"), ("2026", "global scale")]
    ]
    outline = [
        {"section": "Opening", "purpose": "Hook the viewer and frame the question", "duration_pct": 10},
        {"section": "Origins", "purpose": "Build context with the surprising backstory", "duration_pct": 25},
        {"section": "Turning Point", "purpose": "Show the shift that changed everything", "duration_pct": 25},
        {"section": "Current State", "purpose": "What's true today, with concrete examples", "duration_pct": 25},
        {"section": "Takeaway", "purpose": "Land one memorable insight + call to action", "duration_pct": 15},
    ]
    return {
        "summary": f"{topic} is a story of quiet origins, a decisive turning point led by {actor}, and a present moment full of misconceptions — perfect material for a narrative explainer.",
        "findings": findings,
        "timeline": timeline,
        "outline": outline,
        "angles": [a.format(topic=topic) for a in ANGLES],
        "hooks": [h.format(topic=topic) for h in HOOKS],
        "audience": AUDIENCE,
        "trending": bool(r.random() < 0.8),
        "visual_suggestions": [
            "Archive footage and slow pans for the origins section",
            "Kinetic typography for the turning point",
            "Real-world b-roll with data overlays for the current state",
        ],
        "references": [
            {"source": f"National archives — {topic} collection", "accessed": "2026-08"},
            {"source": f"Industry report: State of {topic} 2025–2026", "accessed": "2026-08"},
            {"source": f"Expert commentary compiled by the CineForge research desk", "accessed": "2026-08"},
        ],
    }


# ------------------------------------------------------------------ script
def _build_scenes(topic: str, tone: str, language: str, target_duration: int, r: random.Random) -> list[dict]:
    template = r.choice(SCRIPT_TEMPLATES)
    durations = [int(target_duration * p) for p in (0.10, 0.22, 0.22, 0.24, 0.12)]
    scenes = []
    for i, (label, purpose) in enumerate(
        [
            ("The Hook", "Open on a striking visual; narrator lands the hook and the promise."),
            ("Origins", "Establish the backstory with archive-style visuals and a narrative voice."),
            ("The Turning Point", "Show the shift; raise the stakes; introduce the tension."),
            ("The Current State", "Bring it to today with examples, data overlays and real footage."),
            ("The Takeaway", "Slow down, deliver the insight, end with the call to action."),
        ]
    ):
        line_count = 3 + (i % 3)
        dialogue = []
        for j in range(line_count):
            speaker = "Narrator" if j % 2 == 0 else ("Guest Voice" if i == 2 and j == 1 else "Narrator")
            lines = {
                0: [
                    f"What if everything you thought about {topic} was only half the story?",
                    f"Today, we're pulling back the curtain on {topic} — and the ending might surprise you.",
                    "Stick with me for the next couple of minutes.",
                ],
                1: [
                    f"To understand {topic}, we have to go back — further than most people expect.",
                    f"In those early days, {topic} looked nothing like it does today.",
                    "A handful of people saw what was coming long before anyone else did.",
                ],
                2: [
                    f"Then came the turning point: the moment {topic} stopped being niche and started being everywhere.",
                    "Everything changed — the tools, the rules, the audience.",
                    "And with that shift came a wave of myths that still confuse people today.",
                ],
                3: [
                    f"So where does {topic} stand right now? The short answer: at an inflection point.",
                    "The numbers are moving fast, but the fundamentals are simpler than the hype suggests.",
                    f"Here's the part most coverage gets wrong about {topic}.",
                ],
                4: [
                    f"If you remember one thing about {topic}, make it this: {topic} is a story of people, not machines.",
                    "Now you know the full picture — go use it.",
                    "If this helped, follow for the next chapter. See you in the next one.",
                ],
            }
            dialogue = [{"speaker": "Narrator", "line": line, "emotion": "engaging"} for line in lines[i]]
        scenes.append(
            {
                "id": f"scene-{i + 1}",
                "title": label,
                "purpose": purpose,
                "duration": durations[i],
                "tone": tone,
                "setting": f"Visual: {template['title'].format(topic=topic)} — chapter {i + 1}",
                "dialogue": dialogue,
                "direction": f"Pace per '{TONE_LINES.get(tone, TONE_LINES['cinematic'])}'. Let the strongest visual land on the last line.",
                "transition": ["hard cut", "crossfade", "speed ramp", "match cut", "fade to black"][i],
                "audio_cue": ["music swell + room tone", "subtle riser", "impact hit + music", "music drop", "gentle piano resolution"][i],
            }
        )
    return scenes


def generate_script(topic: str, language: str, tone: str, category: str, target_duration: int, seed: str, research: dict | None) -> dict:
    r = rng(f"script:{seed}:{topic}:{tone}")
    template = r.choice(SCRIPT_TEMPLATES)
    title = template["title"].format(topic=topic.title())
    hook = template["hook"].format(topic=topic)
    scenes = _build_scenes(topic, tone, language, target_duration, r)
    return {
        "title": title,
        "hook": hook,
        "language": language,
        "tone": tone,
        "category": category,
        "structure": "three-act" if category not in ("tutorial", "explainer") else "educational",
        "acts": [{"name": a, "beat": b} for a, b in template["acts"]],
        "scenes": scenes,
        "total_duration": sum(s["duration"] for s in scenes),
        "call_to_action": "Like, share, and subscribe for the next chapter — and comment with your take.",
        "revision": 1,
    }


# --------------------------------------------------------------- storyboard
def generate_storyboard(script: dict, seed: str) -> list[dict]:
    r = rng(f"storyboard:{seed}:{script.get('title', 'Untitled')}")
    comps = ["Rule-of-thirds wide", "Centered close-up", "Dutch-angle medium", "Low-angle hero", "Over-the-shoulder", "Aerial establishing"]
    cams = ["Drone", "Crane", "Handheld", "Steadicam", "Gimbal", "Slider", "Orbit", "Macro"]
    moods = ["mysterious", "uplifting", "tense", "warm", "epic", "intimate"]
    lightings = ["Golden hour rim", "Soft diffused morning", "Moody low-key", "Neon practicals", "High-contrast noir", "Natural window light"]
    panels = []
    for scene in script["scenes"]:
        n = 2 + (int(scene["id"].split("-")[1]) % 3)
        for j in range(n):
            line = scene["dialogue"][j % len(scene["dialogue"])]["line"][:80]
            panels.append(
                {
                    "id": f"{scene['id']}-panel-{j + 1}",
                    "scene_id": scene["id"],
                    "duration": round(scene["duration"] / n, 1),
                    "composition": r.choice(comps),
                    "camera": r.choice(cams),
                    "placement": f"{r.choice(['subject', 'frame edge', 'center frame', 'foreground', 'background'])} — {r.choice(['eye level', 'low angle', 'high angle'])}",
                    "characters": [{"name": "Narrator", "position": r.choice(["left third", "center", "right third"]), "action": r.choice(["walking toward camera", "addressing camera", "gesturing to B-roll", "silent, reacting"])}],
                    "dialogue": line,
                    "lighting": r.choice(lightings),
                    "mood": r.choice(moods),
                    "transition": scene["transition"],
                    "effects": pick(r, ["lens flare", "particle dust", "anamorphic streak", "slow push-in", "rack focus", "none"], 2),
                    "audio_cue": scene["audio_cue"],
                }
            )
    return panels


# ------------------------------------------------------------ scene & shots
def generate_shots(script: dict, environments: list[dict], seed: str) -> list[dict]:
    r = rng(f"shots:{seed}:{script.get('title', 'Untitled')}")
    shot_types = ["Establishing", "Wide", "Medium", "Close-Up", "Extreme Close-Up", "POV", "Over-the-Shoulder", "Hero Shot", "Dutch Angle"]
    camera_types = ["Drone", "Crane", "Handheld", "Steadicam", "Gimbal", "Slider", "FPV", "Orbit", "Underwater", "Macro"]
    lenses = ["14mm", "24mm", "35mm", "50mm", "85mm", "135mm"]
    movements = ["Dolly In", "Dolly Out", "Orbit", "Push In", "Pull Out", "Pan", "Tilt", "Zoom", "Rack Focus", "Truck", "Crane", "Whip Pan", "Static"]
    props = ["none", "coffee cup", "smartphone", "notebook", "vintage radio", "map", "camera rig", "lantern"]
    shots = []
    for scene in script["scenes"]:
        env = environments[(int(scene["id"].split("-")[1]) - 1) % max(1, len(environments))] if environments else {"name": "Studio Set"}
        for j in range(2):
            shots.append(
                {
                    "id": f"{scene['id']}-shot-{j + 1}",
                    "scene_id": scene["id"],
                    "shot_type": r.choice(shot_types),
                    "camera_type": r.choice(camera_types),
                    "lens": r.choice(lenses),
                    "movement": r.choice(movements),
                    "framing": r.choice(["tight", "loose", "medium", "extreme tight"]),
                    "character_action": r.choice(["delivers line to camera", "reacts silently", "walks through frame", "interacts with prop"]),
                    "background": env.get("name", "Studio Set"),
                    "time_of_day": r.choice(["dawn", "golden hour", "midday", "blue hour", "night"]),
                    "weather": r.choice(env.get("weather", ["clear"])) if env.get("weather") else "clear",
                    "props": pick(r, props, 1),
                    "vfx": pick(r, ["sky replacement", "particle system", "cleanup", "set extension", "none"], 2),
                    "duration": round(scene["duration"] / 2, 1),
                }
            )
    return shots


# ------------------------------------------------------------- characters
ARCHETYPES = {
    "host": {"traits": ["warm", "curious", "expressive"], "voice": {"pitch": "medium", "rate": "medium", "style": "conversational"}, "expressions": ["open smile", "raised eyebrow", "thinking look"], "wardrobe": ["dark blazer", "plain tee", "minimal watch"], "palette": ["#e8b04b", "#23262e", "#f5f1e8"]},
    "documentary_narrator": {"traits": ["authoritative", "measured", "observant"], "voice": {"pitch": "low", "rate": "slow", "style": "gravitas"}, "expressions": ["steady gaze", "subtle nod", "concerned brow"], "wardrobe": ["field jacket", "neutral layers"], "palette": ["#8f9aa7", "#1c2128", "#d9dee3"]},
    "expert": {"traits": ["precise", "analytical", "patient"], "voice": {"pitch": "medium-low", "rate": "medium", "style": "lecture"}, "expressions": ["focused", "illustrative hand gestures", "knowing smile"], "wardrobe": ["smart casual", "glasses"], "palette": ["#4f7cac", "#22252b", "#eef1f5"]},
    "storyteller": {"traits": ["expressive", "emotional", "captivating"], "voice": {"pitch": "medium-high", "rate": "varied", "style": "narrative"}, "expressions": ["wide eyes", "warm laugh", "dramatic pause"], "wardrobe": ["vintage knit", "scarf"], "palette": ["#c96f4a", "#2b2320", "#f3e9dc"]},
    "reviewer": {"traits": ["energetic", "direct", "enthusiastic"], "voice": {"pitch": "high", "rate": "fast", "style": "energetic"}, "expressions": ["big grin", "surprised look", "thumbs up"], "wardrobe": ["hoodie", "cap"], "palette": ["#7a5af5", "#16141f", "#ffffff"]},
}


def generate_characters(script: dict, seed: str) -> list[dict]:
    r = rng(f"chars:{seed}:{script.get('title', 'Untitled')}")
    speakers = ["Narrator", "Guest Voice"]
    out = []
    for i, name in enumerate(speakers):
        archetype = r.choice(["host", "documentary_narrator", "expert", "storyteller"])
        base = ARCHETYPES[archetype]
        out.append(
            {
                "name": name,
                "archetype": archetype.replace("_", " ").title(),
                "traits": base["traits"] + [r.choice(["adaptable", "patient", "quick-witted"])],
                "voice": {**base["voice"], "emotion_range": ["calm", "curious", "passionate"]},
                "expressions": base["expressions"],
                "wardrobe": base["wardrobe"],
                "palette": base["palette"],
                "consistency_key": f"ck-{archetype}-{i}",
                "relationship": "Story guide" if i == 0 else "Expert counterpart",
            }
        )
    return out


# ------------------------------------------------------------ environments
def generate_environments(script: dict, seed: str) -> list[dict]:
    r = rng(f"envs:{seed}:{script.get('title', 'Untitled')}")
    return [
        {
            "name": "Cinematic Studio — Softbox Key",
            "category": "studio",
            "description": "Controlled studio space with a large softbox key light and deep backdrop for narrator segments.",
            "lighting": {"key": "softbox 2x3ft", "fill": "40%", "backlight": "warm rim", "color_temp": "5200K"},
            "weather": ["indoor"],
            "time_presets": ["any"],
            "palette": ["#1a1c22", "#e8b04b", "#8a8f98"],
        },
        {
            "name": "Banaue Rice Terraces — Golden Hour",
            "category": "philippine_landmark",
            "description": "The 2,000-year-old terraces of Ifugao at golden hour — sweeping aerial lines, warm light, mist in the valleys.",
            "lighting": {"key": "low golden sun", "fill": "warm bounce", "contrast": "high"},
            "weather": ["clear", "light mist"],
            "time_presets": ["golden hour", "dawn", "blue hour"],
            "palette": ["#d9a441", "#6b8f3a", "#2c3a2a", "#f2e3c2"],
        },
        {
            "name": "Makati Skyline — Cyberpunk Night",
            "category": "urban",
            "description": "Rain-slicked Makati streets at night with neon signage, glass towers and long exposure light trails.",
            "lighting": {"key": "neon practicals", "fill": "cool ambient", "contrast": "extreme"},
            "weather": ["light rain", "clear"],
            "time_presets": ["night", "blue hour"],
            "palette": ["#1b2a4a", "#ff4fa3", "#35d0ff", "#0a0a12"],
        },
        {
            "name": "Vigan Heritage Streets — Overcast Morning",
            "category": "philippine_landmark",
            "description": "Calle Crisologo's cobblestones and colonial facades under soft overcast light — timeless and quiet.",
            "lighting": {"key": "diffused overcast", "fill": "soft ambient", "contrast": "low"},
            "weather": ["overcast", "drizzle"],
            "time_presets": ["morning", "late afternoon"],
            "palette": ["#b9b2a5", "#5a4f44", "#8a8072", "#efe9dd"],
        },
        {
            "name": "Tropical Beach — Sunset",
            "category": "nature",
            "description": "Palawan-style shoreline with limestone cliffs, swaying palms and a warm sunset gradient.",
            "lighting": {"key": "setting sun", "fill": "sea bounce", "contrast": "medium"},
            "weather": ["clear", "trade winds"],
            "time_presets": ["sunset", "golden hour", "midday"],
            "palette": ["#ff9a5c", "#2e6f8e", "#f4d58d", "#12343b"],
        },
        {
            "name": "Rainforest Canopy — Misty Dawn",
            "category": "nature",
            "description": "Luzon rainforest with layered mist, ferns, and god rays breaking through the canopy.",
            "lighting": {"key": "god rays", "fill": "green bounce", "contrast": "soft"},
            "weather": ["mist", "light rain"],
            "time_presets": ["dawn", "morning"],
            "palette": ["#1e3b2a", "#5c8a4a", "#cfe3c0", "#a97c50"],
        },
        {
            "name": "Modern Classroom — Morning",
            "category": "interior",
            "description": "Bright modern classroom with natural window light, whiteboards and soft color accents.",
            "lighting": {"key": "window daylight", "fill": "ceiling ambient", "contrast": "low"},
            "weather": ["sunny"],
            "time_presets": ["morning", "midday"],
            "palette": ["#f2f5f7", "#3f6f8f", "#d98e4a", "#e8edf0"],
        },
        {
            "name": "Orbital Station — Zero Gravity",
            "category": "scifi",
            "description": "A space station corridor with Earth visible through the window — floating dust, cold engineering light.",
            "lighting": {"key": "hard panel light", "fill": "earth bounce", "contrast": "high"},
            "weather": ["vacuum"],
            "time_presets": ["any"],
            "palette": ["#0e1526", "#7fa7c9", "#d8e4ee", "#2c3a52"],
        },
        {
            "name": "Ancient City — Desert Sun",
            "category": "historical",
            "description": "Crumbling sandstone architecture with dust in the air and a harsh desert sun casting long shadows.",
            "lighting": {"key": "hard desert sun", "fill": "sand bounce", "contrast": "very high"},
            "weather": ["clear", "dust storm distant"],
            "time_presets": ["midday", "golden hour"],
            "palette": ["#c9a26a", "#8a5f3c", "#4a3523", "#e8d5ae"],
        },
    ]


# ----------------------------------------------------------- audio & edit
def generate_voice_plan(script: dict, characters: list[dict]) -> dict:
    lines = []
    t = 0.0
    for scene in script["scenes"]:
        per_line = scene["duration"] / max(1, len(scene["dialogue"]))
        for d in scene["dialogue"]:
            lines.append(
                {
                    "scene_id": scene["id"],
                    "speaker": d["speaker"],
                    "text": d["line"],
                    "start": round(t, 1),
                    "end": round(t + per_line, 1),
                    "emotion": d.get("emotion", "neutral"),
                    "pace": "normal",
                }
            )
            t += per_line
    return {
        "narration_tracks": lines,
        "voices": [
            {"character": c["name"], "profile": c["voice"], "cloned": False, "consistency": c["consistency_key"]}
            for c in characters
        ],
        "lip_sync": {"enabled": True, "engine": "wav2lip-compatible"},
        "language": script["language"],
    }


def generate_sound_design(script: dict, seed: str) -> dict:
    r = rng(f"sound:{seed}")
    return {
        "sfx": [
            {"scene_id": s["id"], "cue": s["audio_cue"], "source": "library", "gain_db": -3}
            for s in script["scenes"]
        ],
        "ambience": [{"scene_id": s["id"], "bed": r.choice(["room tone", "city hum", "forest wind", "ocean wash"]), "level": "low"} for s in script["scenes"]],
        "foley": [{"action": "footsteps on mixed surfaces", "detail": "recorded dry, low-passed"}],
        "crowd": [{"scene": "Turning Point", "detail": "distant crowd murmur, 12 voices"}],
    }


def generate_music_plan(script: dict, seed: str) -> dict:
    r = rng(f"music:{seed}")
    tracks = []
    for s in script["scenes"]:
        tracks.append(
            {
                "scene_id": s["id"],
                "title": f"{s['title']} theme",
                "genre": r.choice(["cinematic orchestral", "ambient electronic", "acoustic folk", "neon synthwave"]),
                "mood": r.choice(["building", "introspective", "triumphant", "gentle resolve"]),
                "bpm": r.choice([70, 84, 96, 110]),
                "key": r.choice(["C major", "A minor", "E minor", "G major"]),
            }
        )
    return {"tracks": tracks, "master": {"loudness": "-14 LUFS", "true_peak": "-1.5 dBTP"}, "license": "royalty-free library"}


def generate_edit_plan(script: dict, seed: str) -> dict:
    r = rng(f"edit:{seed}")
    return {
        "assembly": [{"scene_id": s["id"], "order": i + 1, "in_point": "auto-detected", "out_point": "auto-detected", "transition": s["transition"]} for i, s in enumerate(script["scenes"])],
        "smart_cuts": [{"rule": "cut on dialogue pause", "enabled": True}, {"rule": "remove breaths and stumbles", "enabled": True}],
        "b_roll": [{"scene_id": s["id"], "suggested": pick(r, ["detail macro", "time-lapse", "aerial insert", "archive footage", "data overlay"], 2)} for s in script["scenes"]],
        "speed_ramps": [{"scene_id": "scene-3", "profile": "0.5x → 1.2x on impact", "enabled": True}],
        "stabilization": {"enabled": True, "amount": "medium"},
        "color": {"grade": "cineforge 'Golden Cinema' LUT", "contrast": "+8", "warmth": "+5", "shadows": "lifted -2"},
        "motion_tracking": [{"target": "Narrator face", "use": "subtitle anchor"}],
        "timeline_notes": "Assembly targets the hook-to-payoff rhythm; longest shots land on the payoff scene.",
    }


def generate_motion_graphics(script: dict, seed: str) -> dict:
    r = rng(f"mgfx:{seed}")
    return {
        "titles": [{"scene_id": "scene-1", "text": script["title"], "style": "kinetic serif", "duration": 3.0}],
        "lower_thirds": [{"scene_id": s["id"], "text": s["title"], "style": "minimal underline", "duration": 2.5} for s in script["scenes"]],
        "infographics": pick(r, ["key stat callout", "timeline bar", "comparison split", "world map pin", "quote card"], 3),
        "charts": [{"type": "line", "label": "growth curve", "scene": "scene-4"}],
        "icons": pick(r, ["lightbulb", "globe", "chart-up", "play", "quote"], 4),
        "callouts": [{"scene": "scene-4", "text": "KEY INSIGHT", "position": "upper third"}],
    }


# -------------------------------------------------------------- subtitles
def generate_subtitles(voice_plan: dict, language: str) -> dict:
    entries = []
    for i, l in enumerate(voice_plan["narration_tracks"]):
        entries.append(
            {
                "id": f"cap-{i + 1:03d}",
                "start": l["start"],
                "end": l["end"],
                "text": l["text"],
                "speaker": l["speaker"],
                "highlight_word": 0,
            }
        )
    return {
        "entries": entries,
        "language": language,
        "style": {"font": "Inter", "size": "medium", "position": "bottom", "background": "semi-transparent black", "highlight": "amber"},
        "burned_in": False,
        "formats": ["srt", "vtt", "ass", "json"],
    }


# --------------------------------------------------------------- thumbnails
def generate_thumbnails(topic: str, title: str, seed: str) -> list[dict]:
    r = rng(f"thumb:{seed}:{title}")
    concepts = [
        {
            "id": "thumb-1",
            "concept": "The 'Wide-Eyes Reveal'",
            "composition": "Host face at 70% frame right, bold diagonal text frame left, motion blur background",
            "expression": "surprised + curious",
            "contrast": "high",
            "typography": "Condensed 96pt 'WHAT IF?' in amber with black stroke",
            "palette": ["#0a0a0f", "#f5b301", "#ffffff"],
            "ctr_rating": "A+ — emotion + curiosity gap",
        },
        {
            "id": "thumb-2",
            "concept": "The 'Before/After Split'",
            "composition": "Vertical split: desaturated past vs vivid present, subject bridging both halves",
            "expression": "determined",
            "contrast": "very high",
            "typography": "Two-word slab 'THE SHIFT' center-split",
            "palette": ["#3b3b3f", "#d9a441", "#1b4d8f"],
            "ctr_rating": "A — pattern interrupt",
        },
        {
            "id": "thumb-3",
            "concept": "The 'Icon & Subject'",
            "composition": "Subject small, giant glossy icon (lightbulb/globe) over cinematic key art",
            "expression": "confident smile",
            "contrast": "medium",
            "typography": "Outline serif 72pt over icon",
            "palette": ["#16141f", "#7a5af5", "#f2e9dc"],
            "ctr_rating": "B+ — brand-safe, scalable",
        },
    ]
    for c in concepts:
        c["title_text"] = title
    return concepts


# ---------------------------------------------------------------------- seo
def generate_seo(topic: str, title: str, script: dict, seed: str) -> dict:
    r = rng(f"seo:{seed}:{title}")
    chapters = [{"start": 0, "label": "Intro"}, {"start": 20, "label": "Origins"}, {"start": 45, "label": "The Turning Point"}, {"start": 70, "label": "Current State"}, {"start": 95, "label": "Takeaway"}]
    return {
        "titles": [title, f"{title} (Explained in {script['total_duration'] // 60} min)", f"The TRUTH About {topic.title()}"],
        "description": (
            f"{title} — a cinematic deep dive into {topic}. We cover the origins, the turning point everyone missed, "
            f"and where things stand today, with practical takeaways you can actually use.\n\n"
            f"⏱ Chapters:\n" + "\n".join(f"{c['start'] // 60}:{c['start'] % 60:02d} — {c['label']}" for c in chapters) +
            f"\n\n🔔 Subscribe for the next chapter: {script['call_to_action']}"
        ),
        "tags": [topic.lower(), "documentary", "explainer", "cinematic", "storytelling", "deep dive", "facts", "trending", "education", "video essay"],
        "hashtags": ["#Documentary", "#DeepDive", "#Explained", "#VideoEssay", "#Storytelling", "#LearnOnTikTok"],
        "keywords": [f"{topic} explained", f"{topic} history", f"{topic} documentary", f"what is {topic}", f"{topic} 2026"],
        "chapters": chapters,
        "platforms": {
            "youtube": {"title": title, "category": "Education"},
            "tiktok": {"hook_line": script["hook"][:60], "first_3s": "Highest-impact visual + hook text"},
            "instagram": {"caption": script["hook"], "cover": "thumb-1"},
        },
    }


# ---------------------------------------------------------------- analytics
def simulate_analytics(seed: str, views: int = 0) -> dict:
    r = rng(f"stats:{seed}")
    base_views = views or r.randint(4200, 92000)
    retention = [100]
    for i in range(1, 30):
        retention.append(round(retention[-1] * r.uniform(0.90, 0.985), 1))
        if i > 8 and r.random() < 0.2:
            retention[-1] = min(retention[-2], retention[-1] + r.uniform(2, 5))  # second wind
    daily = [
        {"day": f"2026-07-{d:02d}", "views": r.randint(40, 2600), "watch_min": r.randint(30, 900)}
        for d in range(18, 31)
    ] + [
        {"day": f"2026-08-{d:02d}", "views": r.randint(60, 3400), "watch_min": r.randint(50, 1200)}
        for d in range(1, 10)
    ]
    ctr = round(r.uniform(3.4, 9.8), 1)
    return {
        "views": base_views,
        "watch_time_min": round(base_views * r.uniform(0.6, 1.1), 0),
        "avg_retention": round(sum(retention) / len(retention), 1),
        "retention": retention,
        "ctr": ctr,
        "revenue_usd": round(base_views * r.uniform(0.0012, 0.0040), 2),
        "daily": daily,
        "impressions": int(base_views / (ctr / 100)),
    }


# --------------------------------------------------------------- publishing
PUBLISH_PLATFORMS = [
    {"id": "youtube", "name": "YouTube", "api": "YouTube Data API v3", "max_res": "8K", "notes": "Official API — metadata, chapters, monetization, analytics"},
    {"id": "facebook", "name": "Facebook", "api": "Graph API", "max_res": "4K", "notes": "Pages & Groups, scheduled posts"},
    {"id": "tiktok", "name": "TikTok", "api": "Content Posting API", "max_res": "4K", "notes": "Direct post + analytics"},
    {"id": "instagram", "name": "Instagram Reels", "api": "Content Publishing API", "max_res": "4K", "notes": "Reels via professional accounts"},
    {"id": "vimeo", "name": "Vimeo", "api": "Vimeo API", "max_res": "8K", "notes": "Upload, privacy, showcase embeds"},
]
