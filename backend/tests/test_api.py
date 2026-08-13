"""Backend test suite — auth, projects, pipeline, library, render, publish."""
import os
import sys
import time

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_cineforge.db")
os.environ.setdefault("PIPELINE_STAGE_SECONDS", "0.05")
os.environ.setdefault("PIPELINE_FAST", "1")
os.environ.setdefault("CINEFORGE_STILLS", "off")  # keep the suite offline-deterministic
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

# fresh tables per run — no stale jobs/users leak across sessions
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def auth(client):
    r = client.post(
        "/auth/register",
        json={"email": "tester@cineforge.ai", "name": "Test Director", "password": "password123"},
    )
    if r.status_code == 409:  # already registered in this session's db
        r = client.post("/auth/login", json={"email": "tester@cineforge.ai", "password": "password123"})
    assert r.status_code == 200, r.text
    return r.json()


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_auth_flow(client):
    # ensure the account exists for this standalone test
    r = client.post(
        "/auth/register",
        json={"email": "tester@cineforge.ai", "name": "Test Director", "password": "password123"},
    )
    assert r.status_code in (200, 409)
    # login with bad password rejected
    r = client.post("/auth/login", json={"email": "tester@cineforge.ai", "password": "wrong"})
    assert r.status_code == 401
    # me requires token
    assert client.get("/auth/me").status_code == 401
    # valid token works
    r = client.post("/auth/login", json={"email": "tester@cineforge.ai", "password": "password123"})
    token = r.json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "tester@cineforge.ai"


def test_project_crud(client, auth):
    h = {"Authorization": f"Bearer {auth['access_token']}"}
    r = client.post(
        "/projects",
        json={"title": "Test Video", "topic": "Philippine Coffee", "category": "explainer", "tone": "educational", "target_duration": 90},
        headers=h,
    )
    assert r.status_code == 200
    pid = r.json()["id"]
    assert r.json()["stages"] == {}
    # fetch full
    r = client.get(f"/projects/{pid}", headers=h)
    assert r.status_code == 200
    assert r.json()["topic"] == "Philippine Coffee"
    # patch
    r = client.patch(f"/projects/{pid}", json={"tone": "cinematic"}, headers=h)
    assert r.json()["tone"] == "cinematic"
    # unauthorized access
    other = client.post("/auth/register", json={"email": "intruder@cineforge.ai", "name": "Snooper", "password": "password123"})
    if other.status_code == 409:  # leftover from a previous session's db
        other = client.post("/auth/login", json={"email": "intruder@cineforge.ai", "password": "password123"})
    h2 = {"Authorization": f"Bearer {other.json()['access_token']}"}
    assert client.get(f"/projects/{pid}", headers=h2).status_code == 403
    # delete
    assert client.delete(f"/projects/{pid}", headers=h).status_code == 200


def test_pipeline_run_end_to_end(client, auth):
    h = {"Authorization": f"Bearer {auth['access_token']}"}
    r = client.post("/projects", json={"title": "Pipeline E2E", "topic": "Jellyfish Intelligence"}, headers=h)
    pid = r.json()["id"]
    # stages metadata
    stages = client.get("/pipeline/stages", headers=h).json()["stages"]
    assert len(stages) == 18
    assert stages[0]["id"] == "idea" and stages[-1]["id"] == "publishing"
    # run the pipeline
    r = client.post(f"/pipeline/projects/{pid}/run", json={}, headers=h)
    assert r.status_code == 200
    # wait for completion (fast mode ≈ 18 × 0.15s)
    for _ in range(120):
        status = client.get(f"/pipeline/projects/{pid}", headers=h).json()
        if not status["running"] and status["status"] != "in_production":
            break
        time.sleep(0.15)
    status = client.get(f"/pipeline/projects/{pid}", headers=h).json()
    assert status["status"] in ("review", "published")
    assert status["progress"] == 100.0
    # outputs exist for every stage
    full = client.get(f"/projects/{pid}", headers=h).json()
    for sid in ("research", "script", "storyboard", "character_design", "environment_design", "shot_planning", "seo", "thumbnail", "subtitles"):
        assert sid in full["outputs"], f"missing output {sid}"
    assert full["outputs"]["script"]["scenes"][0]["dialogue"]
    assert full["outputs"]["storyboard"]["panels"]
    assert full["outputs"]["shot_planning"]["shots"]
    assert len(full["characters"]) >= 2
    assert len(full["environments"]) >= 4
    # run history recorded
    runs = client.get(f"/pipeline/projects/{pid}/runs", headers=h).json()
    assert runs[0]["status"] == "completed"
    assert runs[0]["stages_completed"] == 18


def test_resume_from_stage(client, auth):
    h = {"Authorization": f"Bearer {auth['access_token']}"}
    r = client.post("/projects", json={"title": "Resume Test", "topic": "Mangroves of Palawan"}, headers=h)
    pid = r.json()["id"]
    client.post(f"/pipeline/projects/{pid}/run", json={"start_stage": "seo"}, headers=h)
    for _ in range(60):
        status = client.get(f"/pipeline/projects/{pid}", headers=h).json()
        if not status["running"]:
            break
        time.sleep(0.15)
    full = client.get(f"/projects/{pid}", headers=h).json()
    assert "seo" in full["outputs"]
    assert "publishing" in full["outputs"]
    # earlier stages stay pending (not run)
    assert full["stages"]["research"]["status"] == "pending"


def test_library_crud(client, auth):
    h = {"Authorization": f"Bearer {auth['access_token']}"}
    r = client.post("/library/characters", json={"name": "Test Host", "archetype": "host", "traits": ["warm"]}, headers=h)
    cid = r.json()["id"]
    assert client.get("/library/characters", headers=h).status_code == 200
    r = client.patch(f"/library/characters/{cid}", json={"name": "Test Host 2", "archetype": "host", "traits": ["warm", "quick"]}, headers=h)
    assert r.json()["name"] == "Test Host 2"
    client.delete(f"/library/characters/{cid}", headers=h)
    # environments
    r = client.post("/library/environments", json={"name": "Test Beach", "category": "nature", "weather": ["clear"]}, headers=h)
    eid = r.json()["id"]
    assert client.delete(f"/library/environments/{eid}", headers=h).status_code == 200


def _wait_job(client, h, jid, timeout=90):
    for _ in range(int(timeout / 0.4)):
        jobs = client.get("/render/jobs", headers=h).json()
        job = next((j for j in jobs if j["id"] == jid), None)
        if job and job["status"] in ("completed", "failed", "cancelled"):
            return job
        time.sleep(0.4)
    return job


def test_render_job_lifecycle(client, auth):
    h = {"Authorization": f"Bearer {auth['access_token']}"}
    r = client.post("/projects", json={"title": "Render Test", "topic": "Laguna Lakes"}, headers=h)
    pid = r.json()["id"]
    r = client.post("/render/jobs", json={"project_id": pid, "scene_label": "scene-1", "model": "auto", "resolution": "480p"}, headers=h)
    assert r.status_code == 200
    jid = r.json()["id"]
    job = _wait_job(client, h, jid)
    assert job["status"] in ("completed", "failed")
    if job["status"] == "completed":
        assert len(job["clips"]) >= 1
        assert all(c["status"] == "completed" for c in job["clips"])
        assert all(c["file_url"] for c in job["clips"])
        assert all(c["score"] and c["score"] > 0 for c in job["clips"])
        import os

        for c in job["clips"]:
            assert os.path.exists(c["file_url"].replace("/media/", "./media/"))
    client.post(f"/render/jobs/{jid}/cancel", headers=h)


def test_video_providers_and_benchmark(client, auth):
    h = {"Authorization": f"Bearer {auth['access_token']}"}
    r = client.get("/video/providers", headers=h)
    assert r.status_code == 200
    data = r.json()
    ids = [p["id"] for p in data["providers"]]
    assert ids == ["veo-3.1", "runway-gen-4.5", "kling-3.0", "seedance-2.0"]
    assert data["benchmark"]["ensemble"]["uplift_pts"] > 0
    r = client.get("/video/benchmark", headers=h)
    assert r.status_code == 200


def test_video_plan_routing(client, auth):
    h = {"Authorization": f"Bearer {auth['access_token']}"}
    r = client.post("/projects", json={"title": "Routing Test", "topic": "Volcano Science", "category": "tiktok", "tone": "energetic"}, headers=h)
    pid = r.json()["id"]
    client.post(f"/pipeline/projects/{pid}/run", json={"start_stage": "video_generation"}, headers=h)
    for _ in range(80):
        status = client.get(f"/pipeline/projects/{pid}", headers=h).json()
        if not status["running"]:
            break
        time.sleep(0.15)
    full = client.get(f"/projects/{pid}", headers=h).json()
    plan = full["outputs"]["video_generation"]
    assert plan["ensemble"]["uplift_pts"] > 0
    scenes = plan["scenes"]
    assert scenes and all(s["clips"] for s in scenes)
    providers = {c["provider"] for s in scenes for c in s["clips"]}
    assert providers <= {"veo-3.1", "runway-gen-4.5", "kling-3.0", "seedance-2.0"}
    for s in scenes:
        for c in s["clips"]:
            assert "shot type" in c["prompt"].lower() or "shot" in c["prompt"].lower()
            assert c["routing"]["chosen"] == c["provider"]


def test_render_produces_media_and_assembles(client, auth):
    h = {"Authorization": f"Bearer {auth['access_token']}"}
    r = client.post("/projects", json={"title": "Media Test", "topic": "Chocolate Hills"}, headers=h)
    pid = r.json()["id"]
    client.post(f"/pipeline/projects/{pid}/run", json={}, headers=h)
    for _ in range(120):
        status = client.get(f"/pipeline/projects/{pid}", headers=h).json()
        if not status["running"]:
            break
        time.sleep(0.15)
    r = client.post("/render/jobs", json={"project_id": pid, "scene_label": "Full timeline", "model": "auto"}, headers=h)
    jid = r.json()["id"]
    job = _wait_job(client, h, jid, timeout=150)
    assert job["status"] == "completed", job.get("error")
    assert len(job["clips"]) >= 4
    # evaluate a scene
    plan = client.get(f"/projects/{pid}", headers=h).json()["outputs"]["video_generation"]
    scene_id = plan["scenes"][0]["scene_id"]
    ev = client.post("/video/evaluate", json={"project_id": pid, "scene_id": scene_id}, headers=h)
    assert ev.status_code == 200
    assert ev.json()["clips"][0]["verdict"] in ("pass", "refine", "regenerate")
    # assemble the final film
    r = client.post(f"/render/jobs/{jid}/assemble", headers=h)
    assert r.status_code == 200
    for _ in range(60):
        job = _wait_job(client, h, jid, timeout=20)
        if job.get("final_url"):
            break
        time.sleep(0.5)
    job = client.get("/render/jobs", headers=h).json()
    job = next(j for j in job if j["id"] == jid)
    assert job["final_url"], job.get("error")
    import os

    assert os.path.exists(job["final_url"].replace("/media/", "./media/"))
    # soundtrack mixed in — real audio stream in the final mp4
    assert job["audio_report"].get("mixed") is True, job["audio_report"]
    assert job["audio_report"].get("music_scenes", 0) > 0
    assert job["audio_report"].get("narration_lines", 0) >= 0  # 0 only if no network for free Edge TTS
    from imageio_ffmpeg import get_ffmpeg_exe
    import subprocess

    probe = subprocess.run(
        [get_ffmpeg_exe(), "-i", job["final_url"].replace("/media/", "./media/")],
        capture_output=True, text=True,
    )
    assert "Audio:" in probe.stderr, probe.stderr[-300:]


def test_audio_synthesis_units():
    from app.services.audio.synth import SR, ambience, impact, music_bed, normalize, write_wav
    from app.services.audio.mix import scene_offsets

    bed = music_bed("cinematic orchestral", "epic", 84, "C major", 2.0, rng_seed=3)
    assert len(bed) == int(2.0 * SR)
    assert float(np.max(np.abs(bed))) > 0.01  # not silent

    a = ambience("ocean", 1.0)
    assert len(a) == SR
    assert float(np.max(np.abs(a))) > 0.0

    fx = impact(0.4)
    assert len(fx) > 0

    fx_padded = np.pad(fx, (0, SR - len(fx)))
    mix = normalize(bed[:SR] + fx_padded * 0.5)
    assert float(np.max(np.abs(mix))) <= 1.0

    from pathlib import Path

    write_wav(Path("./media/audio/test_unit.wav"), bed)
    assert Path("./media/audio/test_unit.wav").exists()

    # scene offsets mirror assembly math
    class C:
        def __init__(self, sid, dur):
            self.scene_id = sid
            self.duration_s = dur

    offs = scene_offsets([C("scene-1", 4.0), C("scene-1", 4.0), C("scene-2", 3.0)])
    assert offs == {"scene-1": 0.0, "scene-2": 8.0}


def test_settings_provider_keys(client, auth):
    import numpy as np  # noqa: F401 (imported here for the unit test above)

    h = {"Authorization": f"Bearer {auth['access_token']}"}
    # save a key
    r = client.put("/settings/providers/kling-3.0", json={"key": "kling_live_abc123secret"}, headers=h)
    assert r.status_code == 200
    assert r.json()["configured"] is True
    assert "••" in r.json()["last4"]
    # list shows it
    r = client.get("/settings/providers", headers=h)
    row = next(p for p in r.json()["providers"] if p["id"] == "kling-3.0")
    assert row["configured"] is True
    assert row["source"] == "db"
    assert row["last4"].endswith("cret")
    # test endpoint accepts it
    r = client.post("/settings/providers/kling-3.0/test", headers=h)
    assert r.status_code == 200
    assert r.json()["ok"] is True
    # unknown provider rejected
    assert client.put("/settings/providers/bogus", json={"key": "xxxxxxxxxxxx"}, headers=h).status_code == 400
    # delete
    assert client.delete("/settings/providers/kling-3.0", headers=h).status_code == 200
    row = next(p for p in client.get("/settings/providers", headers=h).json()["providers"] if p["id"] == "kling-3.0")
    assert row["configured"] is False


def test_audio_defaults(client, auth):
    h = {"Authorization": f"Bearer {auth['access_token']}"}
    r = client.get("/settings/audio", headers=h)
    assert r.status_code == 200
    assert "voices" in r.json()
    r = client.put("/settings/audio", json={"music_style": "neon synthwave", "sfx_enabled": True}, headers=h)
    assert r.json()["audio"]["music_style"] == "neon synthwave"


def test_compare_job(client, auth):
    h = {"Authorization": f"Bearer {auth['access_token']}"}
    r = client.post("/projects", json={"title": "Compare Test", "topic": "Taal Volcano"}, headers=h)
    pid = r.json()["id"]
    r = client.post("/render/jobs", json={"project_id": pid, "scene_label": "0", "model": "compare"}, headers=h)
    jid = r.json()["id"]
    job = _wait_job(client, h, jid, timeout=150)
    assert job["status"] == "completed"
    providers = {c["provider"] for c in job["clips"]}
    assert providers == {"veo-3.1", "runway-gen-4.5", "kling-3.0", "seedance-2.0"}


def test_publish_and_analytics(client, auth):
    h = {"Authorization": f"Bearer {auth['access_token']}"}
    r = client.post("/projects", json={"title": "Publish Test", "topic": "Sinukuan Festival"}, headers=h)
    pid = r.json()["id"]
    r = client.post(f"/projects/{pid}/publish", json={"platform": "youtube"}, headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "published"
    entries = client.get(f"/projects/{pid}/publish", headers=h).json()
    assert entries[0]["platform"] == "youtube"
    an = client.get(f"/projects/{pid}/analytics", headers=h).json()
    assert an["empty"] is False
    ov = client.get("/analytics/overview", headers=h).json()
    assert ov["totals"]["views"] > 0
    assert len(ov["trend"]) > 0


def test_billing_teams_chat(client, auth):
    h = {"Authorization": f"Bearer {auth['access_token']}"}
    plan = client.get("/billing/plan", headers=h).json()
    assert "limits" in plan
    up = client.post("/billing/upgrade", json={"plan": "pro"}, headers=h)
    assert up.json()["plan"] == "pro"
    t = client.post("/teams", json={"name": "Unit Test Studio"}, headers=h)
    assert "id" in t.json()
    chat = client.post("/chat", json={"message": "how do I publish my video?"}, headers=h)
    assert "Publish" in chat.json()["reply"]
