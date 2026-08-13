"""CineForge Video Generation Engine — provider adapters.

Adapter layer for the frontier video models. Each adapter implements the
same contract (available() / generate(spec)), so the pipeline, router and
render queue never care which provider is underneath.

Endpoints mirror the public provider APIs as of 2026-08; exact request
shapes can drift — the adapters are reference-grade and defensive: any
failure falls back to the built-in procedural renderer so a render job
never deadlocks. Drop real API keys in env vars to go live.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ...config import settings

log = logging.getLogger("cineforge.video.providers")


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    name: str
    vendor: str
    api: str
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    max_duration_s: int
    max_res: str
    native_audio: bool
    image_to_video: bool
    video_to_video: bool
    last_frame: bool
    character_consistency: str   # none | reference | strong
    camera_control: str          # prompt | explicit
    price_per_sec: float
    # quality model (0-1) per dimension, from public evals + vendor claims
    quality: dict = field(default_factory=dict)
    # per-provider "director's note" surfaced in the UI
    director_note: str = ""


PROVIDERS: dict[str, ProviderSpec] = {
    "veo-3.1": ProviderSpec(
        id="veo-3.1", name="Google Veo 3.1", vendor="Google DeepMind",
        api="Gemini API — generateVideos (gemini-2.5-flash-preview-veo-3.1)",
        strengths=("photoreal physics & object permanence", "native audio generation", "language-driven camera control", "strong world consistency"),
        weaknesses=("8s clips (extendable)", "premium per-second cost", "not all regions"),
        max_duration_s=8, max_res="1080p", native_audio=True,
        image_to_video=True, video_to_video=True, last_frame=True,
        character_consistency="strong", camera_control="prompt",
        price_per_sec=0.45,
        quality={"motion": 0.96, "physics": 0.98, "consistency": 0.90, "aesthetic": 0.93, "adherence": 0.92, "audio": 0.97},
        director_note="Default for dialogue scenes and anything requiring believable physics — the only frontier model with native audio.",
    ),
    "runway-gen-4.5": ProviderSpec(
        id="runway-gen-4.5", name="Runway Gen-4.5", vendor="Runway AI",
        api="Runway API v1 (api.dev.runwayml.com) — text_to_video / image_to_video",
        strengths=("reference-image character & world consistency", "stylization & editorial look", "image-to-video strength", "long 10s clips"),
        weaknesses=("physics edge cases on complex motion", "premium credits"),
        max_duration_s=10, max_res="4K", native_audio=False,
        image_to_video=True, video_to_video=True, last_frame=False,
        character_consistency="strong", camera_control="prompt",
        price_per_sec=0.35,
        quality={"motion": 0.92, "physics": 0.88, "consistency": 0.95, "aesthetic": 0.95, "adherence": 0.94, "audio": 0.0},
        director_note="Best pick for stylized looks and when a locked character reference image matters more than raw physics.",
    ),
    "kling-3.0": ProviderSpec(
        id="kling-3.0", name="Kling AI 3.0", vendor="Kuaishou",
        api="Kling API (api.klingai.com) — text_to_video, image_to_video, video_extend",
        strengths=("human motion realism", "explicit camera controls (pan/tilt/zoom/rotate)", "strong consistency", "best price/quality balance"),
        weaknesses=("less expressive stylization", "audio handled separately"),
        max_duration_s=10, max_res="1080p", native_audio=False,
        image_to_video=True, video_to_video=True, last_frame=False,
        character_consistency="strong", camera_control="explicit",
        price_per_sec=0.22,
        quality={"motion": 0.95, "physics": 0.92, "consistency": 0.93, "aesthetic": 0.89, "adherence": 0.91, "audio": 0.0},
        director_note="Workhorse for performance shots — explicit camera moves and human motion are its superpowers at a friendly price.",
    ),
    "seedance-2.0": ProviderSpec(
        id="seedance-2.0", name="ByteDance Seedance 2.0", vendor="ByteDance",
        api="Volcano Engine ARK — contents/generations/tasks (doubao-seedance-2-0)",
        strengths=("very long shots (up to 30s)", "multi-shot coherence", "fastest + cheapest", "solid image-to-video"),
        weaknesses=("top-tier realism below Veo", "audio handled separately"),
        max_duration_s=30, max_res="4K", native_audio=False,
        image_to_video=True, video_to_video=True, last_frame=False,
        character_consistency="reference", camera_control="prompt",
        price_per_sec=0.12,
        quality={"motion": 0.90, "physics": 0.89, "consistency": 0.92, "aesthetic": 0.90, "adherence": 0.90, "audio": 0.0},
        director_note="The budget+reach play: 30-second takes and bulk renders at a fraction of the cost.",
    ),
    "pollinations": ProviderSpec(
        id="pollinations", name="Pollinations Live", vendor="Pollinations.AI",
        api="gen.pollinations.ai/video — Wan 2.6 (T2V) / Seedance (I2V), free Seed tier",
        strengths=("free token from enter.pollinations.ai/keys", "real diffusion video (Wan 2.6)", "image-to-video via Seedance", "audio baked into wan output"),
        weaknesses=("shared-GPU queue waits", "720p ceiling on free tier", "rate-limited (5s between requests)"),
        max_duration_s=15, max_res="720p", native_audio=True,
        image_to_video=True, video_to_video=False, last_frame=True,
        character_consistency="reference", camera_control="prompt",
        price_per_sec=0.0,
        quality={"motion": 0.82, "physics": 0.78, "consistency": 0.75, "aesthetic": 0.80, "adherence": 0.85, "audio": 0.9},
        director_note="The free live renderer — default online path. Paste a free token from enter.pollinations.ai/keys in Settings.",
    ),
}

PROVIDER_ORDER = ["veo-3.1", "runway-gen-4.5", "kling-3.0", "seedance-2.0"]

# env var → provider id
KEY_ENV: dict[str, str] = {
    "veo-3.1": "VEO_API_KEY",
    "runway-gen-4.5": "RUNWAY_API_KEY",
    "kling-3.0": "KLING_API_KEY",
    "seedance-2.0": "SEEDANCE_API_KEY",
    "pollinations": "POLLINATIONS_API_KEY",
}


# ------------------------------------------------------------------- client
def resolve_key(provider_id: str, owner_id: str | None = None) -> str | None:
    """Resolve a provider key: user-stored (encrypted DB) first, env fallback."""
    env_attr = KEY_ENV.get(provider_id)
    env_val = getattr(settings, env_attr, "") if env_attr else ""
    if owner_id:
        try:
            from sqlalchemy import select

            from ...db import SessionLocal
            from ...models import ProviderKey
            from ...services.vault import decrypt_secret

            db = SessionLocal()
            try:
                row = db.scalar(select(ProviderKey).where(ProviderKey.user_id == owner_id, ProviderKey.provider == provider_id))
                if row and row.encrypted_key:
                    try:
                        return decrypt_secret(row.encrypted_key)
                    except Exception:  # noqa: BLE001
                        pass
            finally:
                db.close()
        except Exception:  # noqa: BLE001
            pass
    return env_val or None


class ProviderClient:
    """One adapter per provider. generate() always returns a dict with
    {status: ok|mock|failed, file?, thumb?, duration_s?, width?, height?,
     provider_meta?, error?}. On any failure it degrades to the built-in
     procedural renderer (status="mock") so jobs complete offline."""

    def __init__(self, spec: ProviderSpec):
        self.spec = spec

    @property
    def key_env(self) -> str:
        return KEY_ENV[self.spec.id]

    def configured(self, owner_id: str | None = None) -> bool:
        return bool(resolve_key(self.spec.id, owner_id))

    def generate(self, spec: dict, owner_id: str | None = None) -> dict:
        key = resolve_key(self.spec.id, owner_id)
        if not key:
            return self._fallback(spec, "no API key configured — using procedural renderer")
        spec = {**spec, "_api_key": key}
        try:
            return self._generate_live(spec)
        except Exception as exc:  # noqa: BLE001
            log.warning("%s live call failed (%s); falling back to procedural render", self.spec.id, exc)
            return self._fallback(spec, f"provider error ({exc}); used procedural renderer")

    def _fallback(self, spec: dict, reason: str) -> dict:
        from .local import render_clip

        result = render_clip(spec)
        result["status"] = "mock"
        result["provider_meta"] = {"note": reason}
        return result

    # -- live implementations (reference-grade; see provider docs) ----------
    def _generate_live(self, spec: dict) -> dict:
        raise NotImplementedError


class VeoClient(ProviderClient):
    def _generate_live(self, spec: dict) -> dict:
        import httpx

        # Gemini API: POST generateVideos → operation resource → poll → media
        key = spec["_api_key"]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-veo-3.1:generateVideos?key={key}"
        body = {
            "instances": [{"prompt": spec["prompt"], "negativePrompt": spec.get("negative_prompt", "")}],
            "parameters": {
                "durationSeconds": int(spec.get("duration_s", 8)),
                "aspectRatio": spec.get("aspect_ratio", "16:9"),
                "seed": spec.get("seed", 0),
                "outputMimeType": "video/mp4",
            },
        }
        if spec.get("first_frame"):
            body["instances"][0]["image"] = {"gcsUri": spec["first_frame"]}
        if spec.get("last_frame"):
            body["instances"][0]["lastFrame"] = {"gcsUri": spec["last_frame"]}
        with httpx.Client(timeout=120.0) as client:
            op = client.post(url, json=body).raise_for_status().json()
            for _ in range(60):  # poll until done
                op = client.get(op["name"]).raise_for_status().json()
                if op.get("done"):
                    break
                import time

                time.sleep(5)
            video_uri = op.get("response", {}).get("generatedVideos", [{}])[0].get("video", {}).get("uri", "")
        return self._store_download(video_uri, spec, "veo-3.1")

    @staticmethod
    def _store_download(uri: str, spec: dict, source: str = "veo-3.1") -> dict:
        import urllib.request

        data = urllib.request.urlopen(uri, timeout=120).read()
        return _store_bytes(data, spec, source)


class RunwayClient(ProviderClient):
    def _generate_live(self, spec: dict) -> dict:
        import time

        import httpx

        key = spec["_api_key"]
        base = "https://api.dev.runwayml.com/v1"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        body = {
            "model": "gen4_turbo",
            "promptText": spec["prompt"],
            "duration": min(int(spec.get("duration_s", 8)), 10),
            "ratio": spec.get("aspect_ratio", "1280:768"),
            "seed": spec.get("seed", 0),
        }
        if spec.get("first_frame"):
            body["img2img"] = True
        with httpx.Client(timeout=60.0) as client:
            task = client.post(f"{base}/text_to_video", json=body, headers=headers).raise_for_status().json()
            task_id = task["id"]
            for _ in range(120):
                task = client.get(f"{base}/tasks/{task_id}", headers=headers).raise_for_status().json()
                if task.get("status") in ("SUCCEEDED", "FAILED"):
                    break
                time.sleep(3)
            out = task.get("output", [])
            uri = out[0] if isinstance(out, list) and out else ""
        return VeoClient._store_download(uri, spec, "runway-gen-4.5")


class KlingClient(ProviderClient):
    def _generate_live(self, spec: dict) -> dict:
        import time

        import httpx

        key = spec["_api_key"]
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        base = "https://api.klingai.com/v1/videos"
        body = {
            "model_name": "kling-v1",
            "prompt": spec["prompt"],
            "negative_prompt": spec.get("negative_prompt", ""),
            "duration": str(min(int(spec.get("duration_s", 5)), 10)),
            "mode": "std",
            "aspect_ratio": spec.get("aspect_ratio", "16:9"),
            "camera_control": _kling_camera(spec.get("movement", "")),
        }
        with httpx.Client(timeout=60.0) as client:
            task = client.post(f"{base}/text2video", json=body, headers=headers).raise_for_status().json()
            task_id = task["data"]["task_id"]
            for _ in range(120):
                task = client.get(f"{base}/text2video/{task_id}", headers=headers).raise_for_status().json()
                if task["data"]["task_status"] in ("succeed", "failed"):
                    break
                time.sleep(3)
            uri = task["data"].get("task_result", {}).get("videos", [{}])[0].get("url", "")
        return VeoClient._store_download(uri, spec, "kling-3.0")


def _kling_camera(movement: str) -> dict:
    """Map our cinematography vocabulary onto Kling's explicit camera controls."""
    m = (movement or "").lower()
    if "pan" in m:
        return {"type": "pan", "direction": "right" if "whip" not in m else "left"}
    if "tilt" in m:
        return {"type": "tilt", "direction": "up"}
    if "orbit" in m or "crane" in m:
        return {"type": "rotate", "direction": "clockwise"}
    if "push" in m or "dolly in" in m or "zoom" in m:
        return {"type": "zoom", "direction": "in"}
    if "pull" in m or "dolly out" in m:
        return {"type": "zoom", "direction": "out"}
    if "truck" in m:
        return {"type": "horizontal", "direction": "right"}
    return {"type": "static", "direction": "none"}


class SeedanceClient(ProviderClient):
    def _generate_live(self, spec: dict) -> dict:
        import time

        import httpx

        key = spec["_api_key"]
        base = "https://ark.cn-beijing.volces.com/api/v3"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        body = {
            "model": "doubao-seedance-2-0",
            "content": [{"type": "text", "text": spec["prompt"]}],
            "parameters": {
                "duration": min(int(spec.get("duration_s", 10)), 30),
                "resolution": spec.get("aspect_ratio", "16:9"),
                "seed": spec.get("seed", 0),
            },
        }
        with httpx.Client(timeout=60.0) as client:
            task = client.post(f"{base}/contents/generations/tasks", json=body, headers=headers).raise_for_status().json()
            task_id = task["id"]
            for _ in range(240):
                task = client.get(f"{base}/contents/generations/tasks/{task_id}", headers=headers).raise_for_status().json()
                if task["status"] in ("succeeded", "failed"):
                    break
                time.sleep(2)
            if task.get("status") != "succeeded":
                raise RuntimeError("seedance task failed")
            uri = task["content"]["video_url"]
        return VeoClient._store_download(uri, spec, "seedance-2.0")


def _store_bytes(data: bytes, spec: dict, source: str) -> dict:
    """Persist raw video bytes as a clip + thumbnail."""
    import io

    from .local import ensure_media_dir

    out_dir = ensure_media_dir() / "clips" / spec.get("job_id", "standalone")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{spec['clip_id']}.mp4"
    path.write_bytes(data)
    thumb = out_dir / f"{spec['clip_id']}.jpg"
    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as im:
            im.convert("RGB").save(thumb, quality=82)
    except Exception:  # noqa: BLE001
        thumb = None
    return {
        "status": "ok", "file": str(path), "thumb": str(thumb or ""),
        "duration_s": spec.get("duration_s", 8.0),
        "width": spec.get("width", 1280), "height": spec.get("height", 720),
        "provider_meta": {"source": source},
    }


class PollinationsClient(ProviderClient):
    """Free live video generation via gen.pollinations.ai.

    Text-to-video on Wan 2.6; image-to-video via Seedance (the free tier's
    reliable I2V path). Needs only a free token from enter.pollinations.ai/keys
    stored as a key (Settings → Pollinations) or POLLINATIONS_API_KEY.
    Any failure degrades to the built-in procedural renderer."""

    BASE = "https://gen.pollinations.ai/video"

    def configured(self, owner_id: str | None = None) -> bool:
        return bool(resolve_key("pollinations", owner_id))

    def _generate_live(self, spec: dict) -> dict:
        from urllib.parse import quote

        import httpx

        key = spec["_api_key"]
        i2v = bool(spec.get("seed_image_public"))
        model = "seedance" if i2v else "wan"
        dur = max(2, min(int(spec.get("duration_s", 5)), 15))
        if i2v:
            dur = min(dur, 10)  # seedance ceiling
        w, h = int(spec.get("width") or 0), int(spec.get("height") or 0)
        params = {
            "model": model,
            "duration": dur,
            "seed": int(spec.get("seed", 0)),
            "aspectRatio": "9:16" if (w and h and h > w) else "16:9",
            "audio": "true",
        }
        if w and h:
            params["width"] = w
            params["height"] = h
        prompt = spec["prompt"]
        move = (spec.get("movement") or "").strip().lower()
        if move and move not in ("auto", "static", "static lock-off"):
            prompt = f"{prompt} ({move} camera move)"
        if i2v:
            params["image"] = spec["seed_image_public"]
        url = f"{self.BASE}/{quote(prompt)}"
        with httpx.Client(timeout=300.0) as client:
            r = client.get(
                url,
                params=params,
                headers={
                    "Authorization": f"Bearer {key}",
                    "User-Agent": "CineForgeAI/0.1",
                    "Accept": "video/mp4",
                },
            )
            r.raise_for_status()
            data = r.content
        if not data or data[:2] in (b"\xff\xd8", b"\x89P"):
            raise RuntimeError("provider returned an image instead of a video")
        return _store_bytes(data, spec, "pollinations")


def get_client(provider_id: str) -> ProviderClient:
    if provider_id == "image-seed":
        return ImageSeedClient(ProviderSpec(id="image-seed", name="Local Image Animator", description="", url=""))
    spec = PROVIDERS.get(provider_id)
    if not spec:
        raise KeyError(provider_id)
    return {p.id: c for p, c in (
        (PROVIDERS["veo-3.1"], VeoClient(PROVIDERS["veo-3.1"])),
        (PROVIDERS["runway-gen-4.5"], RunwayClient(PROVIDERS["runway-gen-4.5"])),
        (PROVIDERS["kling-3.0"], KlingClient(PROVIDERS["kling-3.0"])),
        (PROVIDERS["seedance-2.0"], SeedanceClient(PROVIDERS["seedance-2.0"])),
        (PROVIDERS["pollinations"], PollinationsClient(PROVIDERS["pollinations"])),
    )}[provider_id]


class ImageSeedClient(ProviderClient):
    """Animated stills: animates an uploaded image with a camera move,
    lighting grade and film grain — fully local, always available."""

    def __init__(self, spec: ProviderSpec):
        self.spec = spec

    def configured(self, owner_id: str | None = None) -> bool:
        return True

    def generate(self, spec: dict, owner_id: str | None = None) -> dict:
        from .local import render_image_clip

        return render_image_clip(spec)
