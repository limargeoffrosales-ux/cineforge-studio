"""Procedural cinematic renderer — real, playable MP4 output offline.

Generates frames with Pillow (environment painting per category, character
figures, lighting overlays, camera movement as crop-window animation, and a
per-provider color grade) and encodes them with ffmpeg. This is the mock
provider path AND the guaranteed-fallback path for live adapters, so every
render job produces an actual video file even with no cloud keys.
"""
from __future__ import annotations

import logging
import math
import os
import random
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

log = logging.getLogger("cineforge.video.local")

MEDIA_ROOT = Path(os.getenv("MEDIA_DIR", "./media")).resolve()


def ensure_media_dir() -> Path:
    MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    return MEDIA_ROOT


def _ffmpeg() -> str:
    from imageio_ffmpeg import get_ffmpeg_exe

    return get_ffmpeg_exe()


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def hex_rgb(hexv: str, fallback: tuple[int, int, int] = (44, 46, 52)) -> tuple[int, int, int]:
    h = str(hexv).lstrip("#")
    if len(h) != 6:
        return fallback
    try:
        return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return fallback


# ------------------------------------------------------------------ styles
STYLE_GRADES = {
    "veo-3.1": {"color": 1.02, "contrast": 1.04, "brightness": 1.0, "grain": 0.05, "grade": "natural"},
    "runway-gen-4.5": {"color": 1.14, "contrast": 1.12, "brightness": 0.97, "grain": 0.02, "grade": "teal-orange editorial"},
    "kling-3.0": {"color": 1.18, "contrast": 1.06, "brightness": 1.02, "grain": 0.03, "grade": "punchy warm"},
    "seedance-2.0": {"color": 1.05, "contrast": 0.98, "brightness": 1.0, "grain": 0.01, "grade": "clean neutral"},
}

MOOD_TINTS = {
    "mysterious": (28, 24, 46), "tense": (30, 22, 22), "intimate": (34, 30, 24),
    "uplifting": (30, 32, 38), "warm": (40, 30, 20), "epic": (24, 30, 40), "neutral": (0, 0, 0),
}


# ------------------------------------------------------------ environment
def paint_background(draw: ImageDraw.ImageDraw, size: tuple[int, int], cat: str, palette: list[str], rng: random.Random) -> None:
    W, H = size
    p0, p1 = palette[0], palette[1] if len(palette) > 1 else "#333340"
    p2 = palette[2] if len(palette) > 2 else "#f5b301"
    cat = cat.lower()

    if "terraces" in cat:
        for i in range(14):  # descending rice terraces
            y = H * 0.35 + i * (H * 0.055)
            shade = 24 + i * 7
            draw.polygon(
                [(0, y), (W * 0.5, y - H * 0.03), (W, y), (W, y + H * 0.05), (0, y + H * 0.05)],
                fill=(60 + shade, 96 + shade, 52 + shade),
            )
        draw.ellipse([W * 0.72 - H * 0.16, H * 0.12, W * 0.72 + H * 0.16, H * 0.12 + H * 0.32], fill=(255, 214, 130, 130))
        return
    if "skyline" in cat or "street" in cat:
        draw.rectangle([0, 0, W, H * 0.42], fill=(10, 12, 26))
        for i in range(22):
            bx = rng.randint(0, W - 30)
            bw = rng.randint(24, 70)
            bh = rng.randint(60, H * 0.5)
            draw.rectangle([bx, H - bh, bx + bw, H], fill=(22 + i % 4 * 4, 26 + i % 3 * 5, 48))
            if rng.random() < 0.55:
                for _ in range(3):
                    wx, wy = rng.randint(bx + 3, bx + bw - 6), rng.randint(int(H - bh) + 6, H - 14)
                    draw.rectangle([wx, wy, wx + 3, wy + 5], fill=(255, 210, 120, 200))
        return
    if "beach" in cat:
        draw.rectangle([0, 0, W, H * 0.55], fill=(255, 150, 90))
        draw.rectangle([0, H * 0.55, W, H], fill=(34, 84, 104))
        for i in range(5):  # wave arcs
            y = H * 0.55 + i * 4
            draw.arc([-W * 0.3, y - 12, W * 1.3, y + 18], 200, 340, fill=(230, 245, 250), width=2)
        draw.ellipse([W * 0.7 - 26, H * 0.3 - 26, W * 0.7 + 26, H * 0.3 + 26], fill=(255, 214, 120))
        # palm
        tx, ty = W * 0.18, H * 0.52
        draw.line([tx, ty, tx - 6, H * 0.95], fill=(70, 48, 30), width=6)
        for ang in range(-40, 41, 20):
            draw.arc([tx - 46, ty - 44, tx + 46, ty + 44], ang, ang + 34, fill=(52, 110, 60), width=7)
        return
    if "forest" in cat or "rainforest" in cat:
        for i in range(10):  # layered pines
            px = rng.randint(0, W)
            ph = rng.randint(H * 0.2, H * 0.5)
            base_y = H * 0.62 + rng.randint(-8, 14)
            for j, k in enumerate((0.9, 0.7, 0.5)):
                w = ph * k * 0.8
                draw.polygon([(px - w, base_y - ph * 0.1 - j * ph * 0.28), (px + w, base_y - ph * 0.1 - j * ph * 0.28), (px, base_y - ph * 0.1 - (j + 1) * ph * 0.3)], fill=(28 + j * 9, 62 + j * 14, 34))
        for _ in range(26):  # god-ray-ish light shafts
            draw.line([(rng.randint(0, W), 0), (rng.randint(0, W), H)], fill=(255, 240, 200, 14), width=2)
        return
    if "interior" in cat or "classroom" in cat:
        draw.rectangle([0, 0, W, H * 0.62], fill=(232, 235, 238))
        draw.rectangle([0, H * 0.62, W, H], fill=(168, 122, 74))
        draw.rectangle([W * 0.1, H * 0.1, W * 0.55, H * 0.5], fill=(190, 214, 230))  # window
        draw.line([W * 0.325, H * 0.1, W * 0.325, H * 0.5], fill=(120, 140, 155), width=2)
        draw.line([W * 0.1, H * 0.3, W * 0.55, H * 0.3], fill=(120, 140, 155), width=2)
        for i in range(4):  # desks
            dx = W * 0.08 + i * W * 0.22
            draw.rounded_rectangle([dx, H * 0.7, dx + W * 0.14, H * 0.76], 4, fill=(110, 76, 46))
        return
    if "space" in cat or "orbital" in cat:
        for _ in range(90):
            sx, sy = rng.randint(0, W), rng.randint(0, int(H * 0.8))
            r = rng.random() * 1.6
            draw.ellipse([sx, sy, sx + r, sy + r], fill=(220, 232, 245, 200))
        draw.ellipse([W * 0.6 - H * 0.42, H * 0.1, W * 0.6 + H * 0.42, H * 0.1 + H * 0.84], outline=(90, 150, 210), width=2)
        draw.arc([W * 0.6 - H * 0.42, H * 0.1, W * 0.6 + H * 0.42, H * 0.1 + H * 0.84], 60, 300, fill=(70, 130, 200), width=10)
        return
    if "ancient" in cat or "desert" in cat:
        draw.rectangle([0, H * 0.3, W, H], fill=(201, 162, 106))
        for i in range(5):  # columns
            cx = W * 0.1 + i * W * 0.2
            draw.rounded_rectangle([cx, H * 0.28, cx + W * 0.05, H * 0.85], 4, fill=(168, 122, 74))
        # arch
        draw.arc([W * 0.32, H * 0.18, W * 0.68, H * 0.75], 0, 180, fill=(168, 122, 74), width=12)
        return
    # studio
    draw.rectangle([0, 0, W, H * 0.58], fill=(24, 26, 32))
    draw.rectangle([0, H * 0.58, W, H], fill=(12, 12, 16))
    draw.ellipse([W * 0.62 - H * 0.22, H * 0.16, W * 0.62 + H * 0.22, H * 0.16 + H * 0.44], fill=(255, 240, 210, 60))
    return


def _int(v: float) -> int:
    return int(round(v))


def draw_character(draw: ImageDraw.ImageDraw, cx: float, cy: float, scale: float, colors: list[str], t: float) -> None:
    """Simple stylized presenter figure (head + torso + arms) with subtle life."""
    bob = math.sin(t * 2.2) * 1.5 * scale
    skin, shirt = (232, 190, 160), colors[0] if colors else (245, 179, 1)
    head_r = 16 * scale
    hy = cy - 34 * scale + bob * 0.4
    draw.ellipse([_int(cx - head_r), _int(hy - head_r), _int(cx + head_r), _int(hy + head_r)], fill=skin)
    draw.ellipse([_int(cx - head_r * 0.85), _int(hy - head_r * 0.85), _int(cx + head_r * 0.85), _int(hy + head_r * 0.85)], outline=(40, 30, 24), width=1)
    draw.rounded_rectangle([_int(cx - 22 * scale), _int(hy + 6 * scale), _int(cx + 22 * scale), _int(hy + 58 * scale)], _int(10 * scale), fill=shirt)
    for side in (-1, 1):  # arms
        ax = cx + side * 22 * scale
        lift = math.sin(t * 1.6 + side) * 6 * scale
        draw.line([_int(ax), _int(hy + 16 * scale), _int(ax + side * 14 * scale), _int(hy + 34 * scale + lift)], fill=shirt, width=_int(5 * scale))
        draw.ellipse([_int(ax + side * 14 * scale - 4 * scale), _int(hy + 32 * scale + lift), _int(ax + side * 14 * scale + 4 * scale), _int(hy + 40 * scale + lift)], fill=skin)
    # shadow
    draw.ellipse([_int(cx - 30 * scale), _int(hy + 62 * scale), _int(cx + 30 * scale), _int(hy + 66 * scale)], fill=(0, 0, 0, 70))


def lighting_overlay(size: tuple[int, int], lighting: str, tod: str, rng: random.Random) -> Image.Image:
    W, H = size
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    light = (lighting or "soft").lower()
    if "golden" in light or "sunset" in light or tod in ("golden hour", "sunset"):
        d.rectangle([0, 0, W, H], fill=(255, 140, 40, 46))
        d.ellipse([W * 0.68 - H * 0.5, H * 0.02, W * 0.68 + H * 0.5, H * 0.02 + H], fill=(255, 190, 80, 60))
    elif "dawn" in light or tod == "dawn":
        d.rectangle([0, 0, W, H], fill=(255, 150, 160, 38))
    elif "night" in light or "neon" in light or tod == "night":
        d.rectangle([0, 0, W, H], fill=(6, 10, 40, 110))
        for _ in range(60):
            sx, sy = rng.randint(0, W), rng.randint(0, int(H * 0.6))
            d.ellipse([sx, sy, sx + 1.4, sy + 1.4], fill=(255, 255, 255, 200))
        if "neon" in light:
            d.ellipse([W * 0.2 - 80, H * 0.4 - 80, W * 0.2 + 80, H * 0.4 + 80], fill=(255, 79, 163, 60))
            d.ellipse([W * 0.8 - 80, H * 0.3 - 80, W * 0.8 + 80, H * 0.3 + 80], fill=(53, 208, 255, 60))
    elif "overcast" in light:
        d.rectangle([0, 0, W, H], fill=(140, 150, 160, 40))
    elif "moody" in light or "low-key" in light:
        d.rectangle([0, 0, W, H], fill=(8, 8, 14, 60))
        d.ellipse([W * 0.3 - 60, H * 0.2 - 60, W * 0.3 + 60, H * 0.2 + 60], fill=(255, 240, 210, 70))
    else:  # soft / diffused / window
        d.ellipse([W * 0.55 - H * 0.7, -H * 0.3, W * 0.55 + H * 0.7, H * 0.7], fill=(255, 245, 225, 46))
    return img


def vignette(size: tuple[int, int], strength: float = 0.42) -> Image.Image:
    W, H = size
    v = Image.new("L", size, 0)
    d = ImageDraw.Draw(v)
    d.ellipse([-W * 0.2, -H * 0.2, W * 1.2, H * 1.2], fill=255)
    v = v.filter(ImageFilter.GaussianBlur(W * 0.22))
    black = Image.new("RGBA", size, (0, 0, 0, int(255 * strength)))
    black.putalpha(ImageChops.invert(v))
    return black


def grade(frame: Image.Image, style: str, rng: random.Random) -> Image.Image:
    g = STYLE_GRADES.get(style, STYLE_GRADES["kling-3.0"])
    frame = ImageEnhance.Color(frame).enhance(g["color"])
    frame = ImageEnhance.Contrast(frame).enhance(g["contrast"])
    frame = ImageEnhance.Brightness(frame).enhance(g["brightness"])
    if g["grain"] > 0:
        noise = Image.new("RGB", frame.size, (0, 0, 0))
        npix = noise.load()
        for y in range(0, frame.height, 2):
            for x in range(0, frame.width, 2):
                v = rng.randint(-28, 28)
                npix[x, y] = (v + 128, v + 128, v + 128)
        noise = noise.resize(frame.size).filter(ImageFilter.GaussianBlur(0.6))
        frame = Image.blend(frame, ImageEnhance.Brightness(noise).enhance(0.4), g["grain"] * 0.5)
    return frame


# ------------------------------------------------------------ camera moves
def crop_box(move: str, t: float, dur: float, W: int, H: int, S: float, rng: random.Random) -> tuple[tuple[int, int, int, int], float]:
    """Returns (box in canvas coords, rotation degrees). Canvas = W*S x H*S."""
    CW, CH = W * S, H * S
    p = clamp(t / max(dur, 0.01), 0, 1)
    cx0, cy0 = CW / 2, CH / 2
    zoom = 0.0
    dx, dy = 0.0, 0.0
    rot = 0.0
    m = move.lower()
    if any(k in m for k in ("push", "dolly in", "zoom in", "zoom")):
        zoom = 0.55 * p
    elif any(k in m for k in ("pull", "dolly out", "zoom out")):
        zoom = 0.55 * (1 - p)
    elif "pan" in m:
        dx = (0.22 * CW) * (1 if "whip" not in m else 2.2) * p
    elif "tilt" in m:
        dy = 0.18 * CH * p
    elif "truck" in m:
        dx = -0.22 * CW * p
    elif "orbit" in m or "crane" in m:
        dx = 0.3 * CW * p
        rot = 3.2 * p if "orbit" in m else 0
    elif "handheld" in m or "gimbal" in m:
        dx, dy = rng.uniform(-0.02, 0.02) * CW, rng.uniform(-0.02, 0.02) * CH
    elif "steadicam" in m:
        dy = 0.06 * CH * p
    elif "rack" in m:
        zoom = 0.06 * math.sin(p * math.pi)
    else:  # static / slider / fpv / macro / underwater
        zoom = 0.015 * math.sin(p * math.pi * 2)
    cw = W * (1 + zoom)
    ch = H * (1 + zoom)
    x = clamp(cx0 - cw / 2 + dx, 0, CW - cw)
    y = clamp(cy0 - ch / 2 + dy, 0, CH - ch)
    return (int(x), int(y), int(x + cw), int(y + ch)), rot


# ----------------------------------------------------------------- image2video
def cover_fit(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Scale/crop an image to exactly fill size (center crop, preserving AR)."""
    w, h = size
    sw, sh = img.size
    scale = max(w / sw, h / sh)
    nw, nh = int(sw * scale + 0.5), int(sh * scale + 0.5)
    img = img.resize((nw, nh), Image.LANCZOS)
    x = (nw - w) // 2
    y = (nh - h) // 2
    return img.crop((x, y, x + w, y + h))


def guess_movement(prompt: str, fallback: str = "push in") -> str:
    """Pick a camera move from the prompt's language."""
    p = (prompt or "").lower()
    if any(k in p for k in ("zoom out", "pull back", "reveal")):
        return "pull back"
    if any(k in p for k in ("pan right", "pan left", "sweep", "panorama")):
        return "whip pan" if any(k in p for k in ("fast", "speed", "quick")) else "pan"
    if any(k in p for k in ("orbit", "around", "rotate")):
        return "orbit"
    if any(k in p for k in ("drift", "float", "soar")):
        return "crane up"
    if any(k in p for k in ("handheld", "shaky", "documentary")):
        return "handheld"
    if any(k in p for k in ("static", "still", "locked")):
        return "static"
    return fallback


def render_image_clip(spec: dict, out_dir: Path | None = None) -> dict:
    """Image-to-video: animate an uploaded image with a camera move, lighting
    grade and film grain — a real playable MP4, fully offline."""
    import time as _time

    rng = random.Random(spec.get("seed", 7) ^ hash(spec.get("clip_id", "image")) & 0xFFFFFFFF)
    W = int(spec.get("width", 480))
    H = int(spec.get("height", 270))
    fps = int(spec.get("fps", 18))
    dur = clamp(float(spec.get("duration_s", 6.0)), 1.0, 30.0)
    S = 1.6
    style = spec.get("provider", "kling-3.0")
    move = spec.get("movement") or guess_movement(spec.get("prompt", ""))
    lighting = spec.get("lighting", "soft")
    mood = spec.get("mood", "neutral")

    src = Path(spec.get("seed_image", ""))
    if not src.exists():
        raise FileNotFoundError(f"seed image not found: {src}")

    with Image.open(src) as raw:
        img = ImageOps.exif_transpose(raw)
        if img.mode != "RGB":
            img = img.convert("RGB")
        img = cover_fit(img, (int(W * S), int(H * S)))
        img = ImageEnhance.Sharpness(img).enhance(1.15)

    out_dir = out_dir or (ensure_media_dir() / "clips" / spec.get("job_id", "standalone"))
    out_dir.mkdir(parents=True, exist_ok=True)
    clip_path = out_dir / f"{spec.get('clip_id', 'image')}.mp4"
    thumb_path = out_dir / f"{spec.get('clip_id', 'image')}.jpg"

    n = int(dur * fps)
    light_static = lighting_overlay((W, H), lighting, "midday", rng)
    vig = vignette((W, H))

    tmp = Path(tempfile.mkdtemp(prefix="cfframes_"))
    t0 = _time.time()
    try:
        for i in range(n):
            t = i / fps
            box, rot = crop_box(move, t, dur, W, H, S, rng)
            frame = img.crop(box).resize((W, H)).convert("RGBA")
            frame = Image.alpha_composite(frame, light_static)
            tint = MOOD_TINTS.get(mood)
            if tint:
                frame = Image.alpha_composite(frame, Image.new("RGBA", (W, H), tint + (26,)))
            frame = Image.alpha_composite(frame, vig)
            frame = grade(frame.convert("RGB"), style, rng)
            frame.save(tmp / f"f_{i:05d}.png")

        subprocess.run(
            [
                _ffmpeg(), "-y", "-framerate", str(fps), "-i", str(tmp / "f_%05d.png"),
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26", "-pix_fmt", "yuv420p",
                "-movflags", "+faststart", str(clip_path),
            ],
            check=True, capture_output=True,
        )
        with Image.open(tmp / "f_00000.png") as first:
            first.convert("RGB").save(thumb_path, quality=80)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    return {
        "status": "ok",
        "file": str(clip_path),
        "thumb": str(thumb_path),
        "duration_s": round(dur, 2),
        "width": W, "height": H,
        "fps": fps,
        "style": style,
        "provider_meta": {
            "source": "image-seed",
            "movement": move,
            "rendered_in_s": round(_time.time() - t0, 1),
        },
    }


# ----------------------------------------------------------------- render
def render_clip(spec: dict, out_dir: Path | None = None) -> dict:
    """Render one clip → mp4 (+ thumbnail jpg). Returns file metadata."""
    rng = random.Random(spec.get("seed", 7) ^ hash(spec.get("clip_id", "clip")) & 0xFFFFFFFF)
    W = int(spec.get("width", 480))
    H = int(spec.get("height", 270))
    fps = int(spec.get("fps", 18))
    dur = clamp(float(spec.get("duration_s", 3.5)), 0.8, 8.0)
    S = 1.6
    style = spec.get("provider", "kling-3.0")
    cat = spec.get("environment_category", "generic")
    palette = spec.get("palette") or ["#2b2b33", "#4a4a55", "#f5b301"]
    move = spec.get("movement", "static")
    lighting = spec.get("lighting", "soft")
    tod = spec.get("time_of_day", "midday")
    mood = spec.get("mood", "neutral")
    char = spec.get("character")

    out_dir = out_dir or (ensure_media_dir() / "clips" / spec.get("job_id", "standalone"))
    out_dir.mkdir(parents=True, exist_ok=True)
    clip_path = out_dir / f"{spec.get('clip_id', 'clip')}.mp4"
    thumb_path = out_dir / f"{spec.get('clip_id', 'clip')}.jpg"

    n = int(dur * fps)
    canvas = (int(W * S), int(H * S))

    # background is static per clip → paint once, then animate the crop
    bg = Image.new("RGB", canvas, (24, 26, 34))
    bd = ImageDraw.Draw(bg)
    top = hex_rgb(palette[0])
    bottom = hex_rgb(palette[1], (51, 51, 64))
    for y in range(canvas[1]):
        f = y / canvas[1]
        c = tuple(int(top[i] + (bottom[i] - top[i]) * f) for i in range(3))
        bd.line([(0, y), (canvas[0], y)], fill=c)
    # painted environment silhouettes on top
    env_img = Image.new("RGBA", canvas, (0, 0, 0, 0))
    paint_background(ImageDraw.Draw(env_img), canvas, cat, palette, rng)
    bg = Image.alpha_composite(bg.convert("RGBA"), env_img).convert("RGB")

    # overlays live in output space (drawn once, composited per frame)
    light_static = lighting_overlay((W, H), lighting, tod, rng)
    vig = vignette((W, H))

    tmp = Path(tempfile.mkdtemp(prefix="cfframes_"))
    try:
        for i in range(n):
            t = i / fps
            box, rot = crop_box(move, t, dur, W, H, S, rng)
            frame = bg.crop(box)
            if rot:
                frame = frame.rotate(-rot, resample=Image.BICUBIC, expand=True)
                frame = frame.resize((W, H))
            else:
                frame = frame.resize((W, H))
            frame = frame.convert("RGBA")

            # character figure (drawn at canvas coords, then cropped by same box)
            if char:
                cf = Image.new("RGBA", canvas, (0, 0, 0, 0))
                pos = char.get("position", "center")
                fcx = {"left third": 0.26, "center": 0.5, "right third": 0.74}.get(pos, 0.5) * canvas[0]
                fcy = canvas[1] * 0.42
                scale = 1.35 * (1 + 0.12 * (t / dur) if "toward" in char.get("action", "") else 1)
                draw_character(ImageDraw.Draw(cf), fcx, fcy, scale, char.get("palette", palette), t)
                # apply camera crop to the character layer too
                cf_crop = cf.crop(box)
                if rot:
                    cf_crop = cf_crop.rotate(-rot, resample=Image.BICUBIC, expand=True).resize((W, H))
                else:
                    cf_crop = cf_crop.resize((W, H))
                frame = Image.alpha_composite(frame, cf_crop)

            # lighting + mood tint + vignette
            frame = Image.alpha_composite(frame, light_static)
            tint = MOOD_TINTS.get(mood)
            if tint:
                tint_layer = Image.new("RGBA", (W, H), tint + (26,))
                frame = Image.alpha_composite(frame, tint_layer)
            frame = Image.alpha_composite(frame, vig)

            frame = grade(frame.convert("RGB"), style, rng)
            frame.save(tmp / f"f_{i:05d}.png")

        subprocess.run(
            [
                _ffmpeg(), "-y", "-framerate", str(fps), "-i", str(tmp / "f_%05d.png"),
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26", "-pix_fmt", "yuv420p",
                "-movflags", "+faststart", str(clip_path),
            ],
            check=True, capture_output=True,
        )
        with Image.open(tmp / "f_00000.png") as first:
            first.convert("RGB").save(thumb_path, quality=80)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    return {
        "status": "ok",
        "file": str(clip_path),
        "thumb": str(thumb_path),
        "duration_s": round(dur, 2),
        "width": W, "height": H,
        "fps": fps,
        "style": style,
        "provider_meta": {"source": "procedural", "grade": STYLE_GRADES.get(style, {})["grade"]},
    }
