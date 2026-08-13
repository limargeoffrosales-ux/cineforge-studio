"""Demo seed: creates the demo user, a library of characters/environments and
two showcase projects — one fully produced, one mid-pipeline."""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import utcnow
from .models import AnalyticsSnapshot, Character, Environment, Project, PublishEntry, Subscription, User
from .security import hash_password
from .services import generators
from .services.pipeline import STAGE_INDEX, initial_stages

log = logging.getLogger("cineforge.seed")


def seed(db: Session) -> None:
    demo = db.scalar(select(User).where(User.email == "demo@cineforge.ai"))
    if not demo:
        demo = User(
            email="demo@cineforge.ai",
            name="Alex Rivera",
            password_hash=hash_password("cineforge123"),
            role="admin",
            plan="studio",
        )
        db.add(demo)
        db.flush()
        db.add(Subscription(user_id=demo.id, plan="studio", usage={"ai_credits": 5800, "renders": 320}))
        log.info("seeded demo user")

    # ---- shared library ----
    if not db.scalar(select(Character).where(Character.is_shared == True).limit(1)):  # noqa: E712
        for i, (name, archetype) in enumerate([("Maya Santos", "host"), ("Dr. Reyes", "expert"), ("Tito Marco", "storyteller")]):
            base = generators.ARCHETYPES[archetype]
            db.add(
                Character(
                    owner_id=demo.id,
                    name=name,
                    archetype=archetype.replace("_", " ").title(),
                    description=f"Shared studio character — {base['voice']['style']} voice, locked appearance.",
                    traits=base["traits"],
                    voice={**base["voice"], "language": "en", "clone_status": "authorized"},
                    expressions=base["expressions"],
                    wardrobe=base["wardrobe"],
                    palette=base["palette"],
                    is_shared=True,
                )
            )
        for env in generators.generate_environments({"scenes": [{"id": f"scene-{i}"} for i in range(1, 6)]}, "seed-lib"):
            db.add(
                Environment(
                    owner_id=demo.id,
                    name=env["name"],
                    category=env["category"],
                    description=env["description"],
                    lighting=env["lighting"],
                    weather=env["weather"],
                    palette=env["palette"],
                    is_shared=True,
                )
            )
        log.info("seeded shared library (characters + environments)")

    # ---- showcase project 1: fully produced documentary ----
    p1 = db.scalar(select(Project).where(Project.topic == "Banaue Rice Terraces"))
    if not p1:
        p1 = Project(
            owner_id=demo.id,
            title="Banaue Rice Terraces: The 2,000-Year Stairway to the Sky",
            topic="Banaue Rice Terraces",
            description="A cinematic documentary on the Ifugao rice terraces — history, engineering and the communities that keep them alive.",
            category="documentary",
            language="en",
            tone="cinematic",
            target_duration=180,
            status="published",
            progress=100.0,
        )
        db.add(p1)
        db.flush()  # assign p1.id before seeding deterministic generators
        _complete_pipeline(db, p1, "Banaue Rice Terraces")
        # publish + analytics
        db.add(PublishEntry(project_id=p1.id, platform="youtube", status="published", url="https://youtube.com/watch/cf-1a2b3c4d"))
        stats = generators.simulate_analytics(p1.id + "youtube", views=48200)
        db.add(AnalyticsSnapshot(project_id=p1.id, **{k: v for k, v in stats.items() if k in ("views", "watch_time_min", "avg_retention", "retention", "ctr", "revenue_usd", "daily")}))
        _seed_demo_clip(db, demo, p1)
        log.info("seeded showcase project: Banaue Rice Terraces")

    # ---- showcase project 2: mid-pipeline explainer ----
    p2 = db.scalar(select(Project).where(Project.topic == "How AI Video Generation Works"))
    if not p2:
        p2 = Project(
            owner_id=demo.id,
            title="How AI Video Generation Actually Works",
            topic="How AI Video Generation Works",
            description="An explainer on diffusion video models, temporal consistency and character locking.",
            category="explainer",
            language="en",
            tone="energetic",
            target_duration=150,
            status="pre_production",
            progress=27.8,
            current_stage="storyboard",
        )
        p2.stages = initial_stages()
        completed = STAGE_INDEX["storyboard"]
        for s in list(p2.stages)[:completed]:
            p2.stages[s]["status"] = "completed"
            p2.stages[s]["progress"] = 100
        p2.stages["storyboard"]["status"] = "running"
        p2.stages["storyboard"]["progress"] = 40
        db.add(p2)
        db.flush()  # assign p2.id before seeding deterministic generators
        p2.outputs["idea"] = generators.generate_research(p2.topic, "en", p2.id) | {"brief": {"topic": p2.topic, "category": "explainer"}}
        p2.outputs["research"] = generators.generate_research(p2.topic, "en", p2.id)
        p2.outputs["script"] = generators.generate_script(p2.topic, "en", "energetic", "explainer", 150, p2.id, p2.outputs["research"])
        p2.outputs["storyboard"] = {"panels": generators.generate_storyboard(p2.outputs["script"], p2.id)[:4], "style_notes": "Rule of thirds default."}
        p2.characters = generators.generate_characters(p2.outputs["script"], p2.id)
        p2.environments = generators.generate_environments(p2.outputs["script"], p2.id)[:4]
        log.info("seeded showcase project: How AI Video Generation Works")
    db.commit()


def _complete_pipeline(db: Session, p: Project, topic: str) -> None:
    from .services.pipeline import initial_stages

    p.stages = initial_stages()
    for s in p.stages.values():
        s["status"] = "completed"
        s["progress"] = 100
    script = generators.generate_script(topic, "en", "cinematic", "documentary", 180, p.id, None)
    p.outputs = {
        "idea": {"brief": {"topic": topic, "category": "documentary", "language": "en", "tone": "cinematic", "target_duration_s": 180}, "selected_angle": "A cinematic journey through the terraces' history, engineering and living culture.", "audience": generators.AUDIENCE},
        "research": generators.generate_research(topic, "en", p.id),
        "script": script,
        "storyboard": {"panels": generators.generate_storyboard(script, p.id), "style_notes": "Rule of thirds default; hero shots reserved for the payoff scene."},
        "scene_planning": {"scenes": [{"id": s["id"], "title": s["title"], "duration": s["duration"], "setting": s["setting"], "props": "none", "environment_family": "philippine_landmark", "weather_default": "clear", "time_of_day": ["dawn", "golden hour", "midday", "night"][i % 4], "vfx_wishlist": "sky replacement"} for i, s in enumerate(script["scenes"])]},
        "character_design": {"characters": generators.generate_characters(script, p.id), "consistency": {"mode": "locked appearance", "face_ref": None}},
        "environment_design": {"environments": generators.generate_environments(script, p.id)},
        "shot_planning": {"shots": generators.generate_shots(script, generators.generate_environments(script, p.id), p.id), "coverage": "2 shots per scene minimum"},
        "video_generation": None,  # filled below with the routed plan
        "voice_generation": generators.generate_voice_plan(script, generators.generate_characters(script, p.id)),
        "sound_design": generators.generate_sound_design(script, p.id),
        "music": generators.generate_music_plan(script, p.id),
        "editing": generators.generate_edit_plan(script, p.id),
        "motion_graphics": generators.generate_motion_graphics(script, p.id),
        "subtitles": generators.generate_subtitles(generators.generate_voice_plan(script, generators.generate_characters(script, p.id)), "en"),
        "thumbnail": {"concepts": generators.generate_thumbnails(topic, script["title"], p.id), "branding": {"watermark": "none"}},
        "seo": generators.generate_seo(topic, script["title"], script, p.id),
        "publishing": {"platforms": generators.PUBLISH_PLATFORMS, "suggested": {"primary": "youtube", "secondary": ["tiktok", "facebook"]}, "status": "published"},
    }
    p.characters = generators.generate_characters(script, p.id)
    p.environments = generators.generate_environments(script, p.id)
    # routed video plan via the real stage function
    try:
        from .services.pipeline import _stage_video

        p.outputs["video_generation"] = _stage_video(p, {})
    except Exception as exc:  # noqa: BLE001
        log.warning("video plan seed failed: %s", exc)
        p.outputs["video_generation"] = {"provider": "auto", "scenes": [], "consistency": {}, "ensemble": {}, "resolutions": ["1080p"], "fps": 30}


def _seed_demo_clip(db: Session, demo: User, project: Project) -> None:
    """Render one real demo clip for the showcase project so the Video Lab
    has playable footage on first login. Best-effort: skipped if rendering
    infrastructure is unavailable."""
    try:
        import uuid

        from .models import RenderJob, VideoClip
        from .services.video.local import render_clip

        spec = {
            "clip_id": "demo-banaue", "job_id": "demo", "provider": "veo-3.1",
            "width": 480, "height": 270, "fps": 18, "duration_s": 4.0, "seed": 2026,
            "movement": "Push In", "composition": "Wide", "camera": "Drone",
            "lighting": "Golden hour", "mood": "epic", "time_of_day": "golden hour",
            "weather": "clear", "background": "Banaue Rice Terraces — Golden Hour",
            "environment_category": "terraces",
            "palette": ["#d9a441", "#6b8f3a", "#2c3a2a", "#f2e3c2"],
            "character": {"name": "Narrator", "palette": ["#e8b04b", "#23262e", "#f5f1e8"], "position": "right third", "action": "addressing camera"},
        }
        result = render_clip(spec)
        job = RenderJob(
            id=uuid.uuid4().hex, owner_id=demo.id, project_id=project.id,
            scene_label="Demo — Banaue Terraces, Veo 3.1 grade", model="auto",
            resolution="480p", status="completed", progress=100.0, duration_s=result["duration_s"],
            finished_at=utcnow(),
        )
        db.add(job)
        db.flush()
        db.add(
            VideoClip(
                job_id=job.id, project_id=project.id, scene_id="scene-1", clip_ref="demo-banaue",
                provider="veo-3.1",
                prompt="Wide aerial drone shot: Banaue Rice Terraces at golden hour, warm mist in the valleys, cinematic color grade, filmic look.",
                status="completed", score=91.4,
                quality={"overall": 91.4, "verdict": "pass", "dims": {"motion_quality": 92, "temporal_consistency": 90, "physics_plausibility": 93, "prompt_adherence": 90, "aesthetics": 92}},
                file_path=result["file"], thumb_path=result.get("thumb", ""),
                width=result["width"], height=result["height"], fps=result["fps"], duration_s=result["duration_s"],
                provider_meta={"source": "procedural", "grade": "natural"},
                completed_at=utcnow(),
            )
        )
        db.commit()
        # assemble the demo film with a full soundtrack so the Video Lab has
        # a finished, audible director's cut on first login.
        from .services.render import render_engine

        render_engine._assemble_worker(job.id)
        log.info("seeded demo clip: %s", result["file"])
    except Exception as exc:  # noqa: BLE001
        log.warning("demo clip seed skipped: %s", exc)
