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


# ------------------------------------------------------------ 2.5D layers
# Parallax factors per depth plane — how far each plane slides vs the
# camera: far barely moves, near sweeps fastest. Sells real depth.
PARALLAX = (0.35, 0.8, 1.25)
S_CANVAS = 2.0  # overscan on the painted canvas (room for pan + parallax)


def _sky(size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    W, H = size
    img = Image.new("RGB", size)
    d = ImageDraw.Draw(img)
    for y in range(H):
        f = y / H
        c = tuple(int(top[i] + (bottom[i] - top[i]) * f) for i in range(3))
        d.line([(0, y), (W, y)], fill=c)
    return img


def _haze(prev: Image.Image, size: tuple[int, int], y0: float, y1: float, tone: tuple[int, int, int], a: int = 90) -> Image.Image:
    """Atmospheric haze band — pulls far planes visually back."""
    W, H = size
    band = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(band)
    for y in range(int(H * y0), int(H * y1)):
        a0 = int(a * (1 - (y / H - y0) / max(0.001, y1 - y0)))
        d.line([(0, y), (W, y)], fill=tone + (a0,))
    return Image.alpha_composite(prev.convert("RGBA"), band)


def paint_far(size: tuple[int, int], cat: str, palette: list[str], rng: random.Random) -> Image.Image:
    """Distant plane: sky, sun/moon, hazy ridges or horizon shapes."""
    W, H = size
    cat = cat.lower()
    p0 = hex_rgb(palette[0])
    p1 = hex_rgb(palette[1], (51, 51, 64))
    if "terraces" in cat or "forest" in cat or "ancient" in cat or "desert" in cat:
        img = _sky(size, p0, p1)
        d = ImageDraw.Draw(img)
        sun_x = 0.72 if rng.random() < 0.8 else 0.3
        d.ellipse([W * sun_x - H * 0.14, H * 0.10 - H * 0.14, W * sun_x + H * 0.14, H * 0.10 + H * 0.14], fill=(255, 224, 160))
        ridge_y = 0.52 + rng.uniform(-0.04, 0.04)
        for i in range(5):  # hazy distant ridges
            ry = H * ridge_y + i * H * 0.045
            shade = 90 + i * 18
            d.polygon([(0, H), (W * 0.22, ry - H * 0.02), (W * 0.5, ry), (W * 0.78, ry + H * 0.01), (W, ry - H * 0.01), (W, H)], fill=(shade, shade + 8, shade + 22))
        return _haze(img, size, ridge_y - 0.10, ridge_y + 0.06, p1, 70)
    if "skyline" in cat or "street" in cat:
        img = _sky(size, (8, 10, 26), (24, 20, 44))
        d = ImageDraw.Draw(img)
        for _ in range(70):
            sx, sy = rng.randint(0, W), rng.randint(0, int(H * 0.55))
            r = rng.random() * 1.4
            d.ellipse([sx, sy, sx + r, sy + r], fill=(210, 224, 244, 180))
        for i in range(8):  # far tower band
            bx = i * W / 8 + rng.randint(-14, 14)
            bw = W / 10 + rng.randint(6, 26)
            bh = H * rng.uniform(0.14, 0.3)
            d.rectangle([bx, H * 0.62 - bh, bx + bw, H * 0.62], fill=(34 + i * 3, 38 + i * 2, 66))
        return _haze(img, size, 0.50, 0.64, (20, 18, 40), 60)
    if "beach" in cat:
        img = _sky(size, (255, 160, 90), (255, 210, 160))
        d = ImageDraw.Draw(img)
        d.ellipse([W * 0.7 - H * 0.13, H * 0.12 - H * 0.13, W * 0.7 + H * 0.13, H * 0.12 + H * 0.13], fill=(255, 236, 190))
        for i in range(5):  # clouds
            cw = W * rng.uniform(0.1, 0.22)
            cx0 = rng.uniform(0, W)
            cy0 = H * rng.uniform(0.18, 0.4)
            d.ellipse([cx0, cy0, cx0 + cw, cy0 + H * 0.04], fill=(255, 230, 200, 210))
        return img.convert("RGBA")
    if "interior" in cat or "classroom" in cat:
        img = _sky(size, (120, 130, 140), (200, 205, 210))
        d = ImageDraw.Draw(img)
        d.rectangle([W * 0.08, H * 0.06, W * 0.5, H * 0.46], fill=(170, 200, 220))  # window
        d.line([W * 0.29, H * 0.06, W * 0.29, H * 0.46], fill=(120, 140, 155), width=3)
        d.line([W * 0.08, H * 0.26, W * 0.5, H * 0.26], fill=(120, 140, 155), width=3)
        return img.convert("RGBA")
    if "space" in cat or "orbital" in cat:
        img = _sky(size, (4, 4, 12), (10, 8, 26))
        d = ImageDraw.Draw(img)
        for _ in range(110):
            sx, sy = rng.randint(0, W), rng.randint(0, int(H * 0.9))
            r = rng.random() * 1.5
            d.ellipse([sx, sy, sx + r, sy + r], fill=(220, 232, 245, 210))
        d.ellipse([W * 0.62 - H * 0.4, H * 0.12, W * 0.62 + H * 0.4, H * 0.12 + H * 0.8], outline=(90, 150, 210), width=2)
        d.arc([W * 0.62 - H * 0.4, H * 0.12, W * 0.62 + H * 0.4, H * 0.12 + H * 0.8], 55, 305, fill=(70, 130, 200), width=10)
        return img.convert("RGBA")
    # studio
    img = _sky(size, (18, 20, 26), (34, 36, 44))
    return img.convert("RGBA")


def paint_mid(size: tuple[int, int], cat: str, palette: list[str], rng: random.Random) -> Image.Image:
    """Mid plane: the hero elements of each environment."""
    W, H = size
    cat = cat.lower()
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if "terraces" in cat:
        for i in range(8):  # upper terrace bands
            y = H * 0.36 + i * (H * 0.05)
            shade = 30 + i * 6
            d.polygon([(0, y), (W * 0.5, y - H * 0.025), (W, y), (W, y + H * 0.045), (0, y + H * 0.045)], fill=(66 + shade, 104 + shade, 56 + shade))
    elif "skyline" in cat or "street" in cat:
        for i in range(16):  # main towers
            bx = rng.randint(0, W - 40)
            bw = rng.randint(28, 78)
            bh = rng.randint(80, int(H * 0.62))
            d.rectangle([bx, H - bh, bx + bw, H], fill=(26 + i % 4 * 5, 30 + i % 3 * 6, 56))
            if rng.random() < 0.6:
                for _ in range(4):
                    wx, wy = rng.randint(bx + 3, bx + bw - 8), rng.randint(int(H - bh) + 8, H - 16)
                    d.rectangle([wx, wy, wx + 3, wy + 5], fill=(255, 210, 120, 210))
    elif "beach" in cat:
        d.rectangle([0, H * 0.52, W, H], fill=(30, 80, 100))
        for i in range(6):  # wave arcs
            y = H * 0.52 + i * 4
            d.arc([-W * 0.3, y - 12, W * 1.3, y + 18], 200, 340, fill=(225, 242, 248), width=2)
    elif "forest" in cat or "rainforest" in cat:
        for i in range(12):  # tree line
            px = rng.randint(0, W)
            ph = rng.randint(int(H * 0.22), int(H * 0.45))
            base_y = H * 0.66 + rng.randint(-6, 12)
            for j, k in enumerate((0.9, 0.7, 0.5)):
                w = ph * k * 0.8
                d.polygon([(px - w, base_y - ph * 0.1 - j * ph * 0.28), (px + w, base_y - ph * 0.1 - j * ph * 0.28), (px, base_y - ph * 0.1 - (j + 1) * ph * 0.3)], fill=(30 + j * 10, 66 + j * 16, 36))
        for _ in range(18):  # god-rays
            d.line([(rng.randint(0, W), 0), (rng.randint(0, W), H)], fill=(255, 240, 200, 12), width=2)
    elif "interior" in cat or "classroom" in cat:
        d.rectangle([0, H * 0.6, W, H], fill=(150, 108, 66))
        for i in range(5):  # desks
            dx = W * 0.06 + i * W * 0.19
            d.rounded_rectangle([dx, H * 0.68, dx + W * 0.15, H * 0.74], 4, fill=(104, 72, 44))
        d.polygon([(W * 0.55, H * 0.30), (W * 0.95, H * 0.16), (W, H * 0.62), (W * 0.55, H * 0.62)], fill=(56, 68, 80))  # board
    elif "space" in cat or "orbital" in cat:
        d.ellipse([W * 0.18 - H * 0.2, H * 0.55 - H * 0.2, W * 0.18 + H * 0.2, H * 0.55 + H * 0.2], fill=(150, 160, 185))
        d.rectangle([W * 0.3, H * 0.52, W * 0.9, H * 0.56], fill=(60, 70, 90))  # station truss
        for i in range(5):
            d.polygon([(W * (0.32 + i * 0.12), H * 0.52), (W * (0.32 + i * 0.12) + 12, H * 0.40), (W * (0.32 + i * 0.12) + 26, H * 0.52)], fill=(70, 92, 120))
    elif "ancient" in cat or "desert" in cat:
        d.rectangle([0, H * 0.34, W, H], fill=(196, 158, 106))
        for i in range(5):  # columns
            cx = W * 0.1 + i * W * 0.2
            d.rounded_rectangle([cx, H * 0.30, cx + W * 0.05, H * 0.82], 4, fill=(158, 114, 70))
        d.arc([W * 0.32, H * 0.20, W * 0.68, H * 0.72], 0, 180, fill=(158, 114, 70), width=12)
    else:  # studio
        d.rectangle([0, H * 0.56, W, H], fill=(12, 12, 16))
        d.ellipse([W * 0.62 - H * 0.22, H * 0.14, W * 0.62 + H * 0.22, H * 0.14 + H * 0.44], fill=(255, 240, 210, 66))
        d.polygon([(W * 0.2, H * 0.56), (W * 0.3, H * 0.14), (W * 0.44, H * 0.14), (W * 0.34, H * 0.56)], fill=(70, 74, 86))  # backdrop panel
    return img


def paint_near(size: tuple[int, int], cat: str, palette: list[str], rng: random.Random) -> Image.Image:
    """Foreground plane: dark silhouettes + DOF blur → strongest depth cue."""
    W, H = size
    cat = cat.lower()
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if "terraces" in cat:
        for i in range(7):
            y = H * 0.40 + i * (H * 0.075)
            shade = 14 + i * 10
            d.polygon([(0, y), (W * 0.5, y - H * 0.04), (W, y), (W, y + H * 0.06), (0, y + H * 0.06)], fill=(40 + shade, 74 + shade, 34 + shade))
        d.polygon([(0, H * 0.86), (W * 0.5, H * 0.80), (W, H * 0.86), (W, H), (0, H)], fill=(18, 40, 20))
    elif "skyline" in cat or "street" in cat:
        d.polygon([(0, H * 0.78), (W * 0.12, H * 0.66), (W * 0.2, H * 0.84), (W * 0.3, H * 0.72), (W * 0.45, H * 0.9), (W * 0.62, H * 0.78), (W * 0.8, H * 0.94), (W, H * 0.82), (W, H), (0, H)], fill=(8, 9, 16))
        for i in range(3):  # street lamps
            lx = W * (0.12 + i * 0.36)
            d.line([lx, H * 0.98, lx, H * 0.74], fill=(10, 12, 20), width=4)
            d.ellipse([lx - 10, H * 0.74 - 10, lx + 10, H * 0.74 + 10], fill=(255, 210, 130, 210))
    elif "beach" in cat:
        d.polygon([(0, H * 0.62), (W, H * 0.70), (W, H), (0, H)], fill=(196, 168, 120))
        tx, ty = W * 0.16, H * 0.56
        d.line([tx, ty, tx - 5, H * 0.98], fill=(54, 38, 24), width=7)
        for ang in range(-40, 41, 18):
            d.arc([tx - 52, ty - 50, tx + 52, ty + 50], ang, ang + 36, fill=(38, 84, 46), width=8)
        d.ellipse([W * 0.55, H * 0.93, W * 0.95, H * 1.02], fill=(240, 244, 246, 170))  # foam edge
        tx2, ty2 = W * 0.8, H * 0.60
        d.line([tx2, ty2, tx2 - 4, H * 0.98], fill=(40, 30, 20), width=6)
        for ang in range(-30, 41, 20):
            d.arc([tx2 - 40, ty2 - 40, tx2 + 40, ty2 + 40], ang, ang + 32, fill=(30, 70, 40), width=7)
    elif "forest" in cat or "rainforest" in cat:
        for _ in range(3):  # huge dim trunks framing the shot
            px = rng.choice((rng.randint(0, W // 8), rng.randint(W * 7 // 8, W)))
            d.rectangle([px, H * 0.2, px + rng.randint(14, 26), H], fill=(12, 16, 12))
            d.ellipse([px - 24, H * 0.06, px + 30, H * 0.22], fill=(10, 14, 10))
    elif "interior" in cat or "classroom" in cat:
        d.polygon([(0, H * 0.97), (W * 0.4, H * 0.90), (W, H * 0.97), (W, H), (0, H)], fill=(84, 60, 40))
        d.ellipse([W * 0.78 - 26, H * 0.80 - 26, W * 0.78 + 26, H * 0.80 + 26], fill=(60, 92, 60))  # plant
        d.line([W * 0.78, H * 0.80, W * 0.78, H * 0.96], fill=(50, 40, 30), width=4)
    elif "space" in cat or "orbital" in cat:
        d.polygon([(0, H * 0.70), (W * 0.14, H * 0.62), (W * 0.22, H * 0.78), (W * 0.34, H * 0.58), (W * 0.44, H * 0.8), (W, H * 0.62), (W, H), (0, H)], fill=(16, 18, 28))
        for i in range(4):  # blinking nav lights
            nx, ny = W * (0.08 + i * 0.26), H * (0.70 + (i % 2) * 0.06)
            d.ellipse([nx - 3, ny - 3, nx + 3, ny + 3], fill=(255, 90, 90, 220) if i % 2 else (120, 255, 255, 220))
    elif "ancient" in cat or "desert" in cat:
        d.polygon([(0, H * 0.76), (W * 0.16, H * 0.68), (W * 0.3, H * 0.82), (W * 0.5, H * 0.74), (W * 0.72, H * 0.86), (W * 0.9, H * 0.72), (W, H * 0.8), (W, H), (0, H)], fill=(90, 62, 32))
    else:  # studio
        d.rectangle([0, H * 0.88, W, H], fill=(8, 8, 10))
        d.polygon([(0, H * 0.84), (W * 0.1, H * 0.72), (W * 0.18, H * 0.84), (W * 0.24, H * 0.78), (W, H * 0.92), (W, H), (0, H)], fill=(16, 17, 20))
    return img.filter(ImageFilter.GaussianBlur(1.4))  # shallow DOF


def atmosphere(size: tuple[int, int], cat: str, t: float, rng: random.Random,
               weather: str = "", tod: str = "midday", mood: str = "neutral") -> Image.Image:
    """Per-frame drifting foreground element — fog band, dust motes or
    weather particles driven by the shot's time of day / weather."""
    W, H = size
    cat = cat.lower()
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    wx = (weather or "").lower()
    ctx = (tod or "") + " " + wx + " " + (mood or "")
    raining = any(k in ctx for k in ("rain", "drizzle", "mist", "overcast"))
    snowing = any(k in ctx for k in ("winter", "snow", "cold"))
    night = "night" in tod or "night" in wx
    embers = night and any(k in cat for k in ("desert", "ancient", "space", "city", "street"))
    fireflies = night and any(k in cat for k in ("forest", "rainforest", "interior"))
    if raining:
        for _ in range(42):
            r0, r1 = rng.random(), rng.random()
            x = (r0 * (W + 90) - 45 + t * 240 * (0.6 + r0 * 0.9)) % (W + 90) - 45
            y = (r1 * H + t * 520) % H
            ln = 10 + r0 * 8
            d.line([x, y, x - ln * 0.22, y + ln], fill=(205, 215, 228, rng.randint(30, 75)), width=1)
    elif snowing:
        for _ in range(30):
            r0 = rng.random()
            x = (r0 * W + t * 22 * (0.5 + r0)) % W
            y = (rng.random() * H + t * 38) % H
            x += math.sin(t * 1.7 + r0 * 9.1) * 14
            r = 1.1 + r0 * 1.6
            d.ellipse([x - r, y - r, x + r, y + r], fill=(248, 250, 252, rng.randint(80, 170)))
    elif embers:
        for _ in range(16):
            r0 = rng.random()
            x = (r0 * W + math.sin(t * 0.8 + r0 * 7.3) * 26) % W
            y = (H * 0.75 - t * 46 * r0 - rng.random() * H * 0.2) % H
            r = 1.2 + r0 * 1.8
            d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 160 + rng.randint(0, 60), 60, rng.randint(60, 190)))
    elif fireflies:
        for _ in range(12):
            r0 = rng.random()
            x = (r0 * W * 1.2 + math.sin(t * 0.5 + r0 * 11) * 30) % (W * 1.2)
            y = rng.random() * H * 0.7 + (t * 6) % (H * 0.3) + math.sin(t * 1.3 + r0 * 5) * 12
            a = rng.randint(40, 140) + int(70 * math.sin(t * 2.6 + r0 * 8.7))
            d.ellipse([x - 1.6, y - 1.6, x + 1.6, y + 1.6], fill=(188, 255, 120, max(20, min(200, a))))
    elif any(k in cat for k in ("forest", "ancient", "terraces", "interior")):
        drift = (t * 6) % (W + 400) - 200
        for i in range(3):
            fw = W * 0.5
            fx = drift + i * W * 0.42 - W * 0.25
            fy = H * rng.uniform(0.55, 0.8)
            d.ellipse([fx, fy, fx + fw, fy + H * 0.05], fill=(235, 238, 244, 26))
    else:
        for _ in range(rng.randint(12, 26)):  # dust motes in the light
            mx = (rng.random() * W + t * rng.uniform(2, 9)) % W
            my = rng.random() * H
            r = rng.random() * 1.6 + 0.4
            d.ellipse([mx - r, my - r, mx + r, my + r], fill=(255, 244, 220, rng.randint(18, 60)))
    return layer.filter(ImageFilter.GaussianBlur(1.1))


def env_anim(size: tuple[int, int], cat: str, t: float, rng: random.Random) -> Image.Image:
    """Animated environment details — shimmer, flicker, drifting light —
    so even locked-off shots read as living scenes."""
    W, H = size
    cat = cat.lower()
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    if any(k in cat for k in ("terraces", "beach")):
        for i in range(3):  # water shimmer streaks
            sx = (t * (26 + i * 9) + i * W * 0.33) % (W + 260) - 130
            sy = H * (0.52 + i * 0.12)
            pulse = 0.6 + 0.4 * math.sin(t * 2.1 + i * 2.4)
            d.ellipse([sx, sy, sx + W * (0.16 + i * 0.05), sy + H * 0.012], fill=(240, 250, 255, int(26 * pulse)))
    elif "skyline" in cat or "street" in cat:
        for i in range(6):  # window lights flickering in the dark
            fx = (i * 997) % W
            fy = H * (0.22 + ((i * 313) % 34) / 100)
            a = int(60 + 90 * abs(math.sin(t * (1.5 + i * 0.7) + i * 2.3)))
            d.rectangle([fx, fy, fx + 4 + (i % 2) * 3, fy + 7], fill=(255, 208, 120, a))
        if "street" in cat:
            for i in range(2):  # passing headlight glow
                hy = H * (0.90 + (i * 0.05) * math.sin(t * 0.6 + i))
                d.ellipse([W * (0.2 + i * 0.5) - 30, hy, W * (0.2 + i * 0.5) + 30, hy + H * 0.03], fill=(255, 240, 200, 22))
    elif "forest" in cat or "rainforest" in cat:
        for i in range(2):  # god rays swaying slowly
            gx = W * (0.28 + i * 0.4) + math.sin(t * 0.35 + i * 3.1) * W * 0.06
            d.polygon([(gx - 14, 0), (gx + 14, 0), (gx + W * 0.07, H * 0.75), (gx - W * 0.05, H * 0.75)], fill=(255, 240, 200, int(12 + 6 * math.sin(t * 0.8 + i))))
    elif "space" in cat or "orbital" in cat:
        for i in range(5):  # twinkling stars
            sx = (i * 919 + 40) % W
            sy = (i * 571) % int(H * 0.8)
            r = 1.0 + (0.7 if i == 3 else 0)
            a = int(110 + 90 * math.sin(t * (2.0 + i * 0.53) + i * 5))
            d.ellipse([sx - r, sy - r, sx + r, sy + r], fill=(230, 240, 252, max(25, a)))
    elif "ancient" in cat or "desert" in cat:
        for i in range(3):  # rising heat shimmer bands
            by = (H * 0.42 - t * 6.0 * (1 + i * 0.3) + i * H * 0.1) % (H * 0.5)
            d.arc([-W * 0.2, by, W * 1.2, by + H * 0.06], 20, 160, fill=(255, 210, 130, 14), width=3)
    elif "interior" in cat or "classroom" in cat:
        a = int(10 + 6 * math.sin(t * 1.3))  # projector beam breathing
        d.polygon([(W * 0.08, H * 0.06), (W * 0.5, H * 0.06), (W * 0.72, H * 0.62), (W * 0.3, H * 0.62)], fill=(255, 250, 230, a))
    else:  # studio
        a = int(46 + 22 * math.sin(t * 2.2))  # softbox flicker
        d.ellipse([W * 0.62 - H * 0.22 - 6, H * 0.16 - 6, W * 0.62 + H * 0.22 + 6, H * 0.16 + H * 0.44 + 6], fill=(255, 240, 210, a))
    return layer


def camera_window(move: str, t: float, dur: float, W: int, H: int, rng: random.Random) -> tuple[float, float, float, float, float]:
    """(cx, cy, zoom, rot) in canvas coords — organic, layered camera work.

    Positional moves run on a smoothstep curve with a soft settle so pans,
    trucks and craning feel like a real operator, not a linear tween."""
    p = clamp(t / max(dur, 0.01), 0, 1)
    e = p * p * (3 - 2 * p)  # smoothstep
    settle = math.sin(p * math.pi)  # ease-out overshoot/settle envelope
    CW, CH = W * S_CANVAS, H * S_CANVAS
    zoom, dx, dy, rot = 0.0, 0.0, 0.0, 0.0
    m = (move or "").lower()
    if any(k in m for k in ("push", "dolly in", "zoom in")):
        zoom = 0.5 * e + 0.02 * settle
    elif any(k in m for k in ("pull", "dolly out", "zoom out", "reveal")):
        zoom = 0.5 * (1 - e) + 0.02 * settle
    elif any(k in m for k in ("pan", "sweep", "whip")):
        dx = 0.18 * CW * (2.4 if "whip" in m else 1.0) * e
    elif "tilt" in m:
        dy = 0.16 * CH * e
    elif "truck" in m:
        dx = -0.18 * CW * e
    elif "orbit" in m or "around" in m:
        dx = 0.24 * CW * e
        dy = 0.05 * CH * math.sin(p * math.pi)
        rot = 2.4 * e
    elif "crane" in m:
        dy = -0.13 * CH * e
    elif "handheld" in m or "shaky" in m:
        zoom = 0.03 * math.sin(p * math.pi)
        dx = (math.sin(t * 3.1) + 0.5 * math.sin(t * 7.3)) * 0.019 * CW
        dy = (math.sin(t * 2.3 + 1.7) + 0.5 * math.sin(t * 6.1)) * 0.016 * CH
        rot = (math.sin(t * 1.9) + math.sin(t * 4.7)) * 0.8
    elif any(k in m for k in ("steadicam", "float", "soar", "drift", "glide")):
        dy = 0.09 * CH * e
        dx = 0.05 * CW * e
        rot = 0.6 * e
    elif any(k in m for k in ("rack", "macro")):
        zoom = 0.10 * math.sin(p * math.pi)
    elif "gimbal" in m:
        dx = 0.05 * CW * e
        rot = 1.1 * e
    else:  # static / slider / fpv / underwater / ""
        zoom = 0.02 * math.sin(p * math.pi * 3)
        dx = 0.03 * CW * math.sin(p * math.pi * 2)
        dy = 0.012 * CH * math.sin(p * math.pi * 1.3)
    return CW / 2 + dx, CH / 2 + dy, zoom, rot, p


def compose_2d5(
    far: Image.Image,
    mid: Image.Image,
    near: Image.Image,
    W: int,
    H: int,
    cam: tuple[float, float, float, float, float],
    char_layer: Image.Image | None,
    vfx: Image.Image | None,
) -> Image.Image:
    """Compose one frame from depth planes with per-plane parallax windows."""
    cx, cy, zoom, _rot, _p = cam
    CW, CH = W * S_CANVAS, H * S_CANVAS
    ww, wh = W * (1 + zoom), H * (1 + zoom)
    planes = (far, mid, near)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    for i, plane in enumerate(planes):
        pf = PARALLAX[i]
        cxi = cx + (cx - CW / 2) * pf * max(zoom, 0.0) * 1.6
        cyi = cy + (cy - CH / 2) * pf * max(zoom, 0.0) * 1.6
        wi = ww * (1 - (pf - 0.8) * zoom * 0.55)
        hi = wh * (1 - (pf - 0.8) * zoom * 0.55)
        wi = max(wi, W * 0.2)
        hi = max(hi, H * 0.2)
        cxi = clamp(cxi, wi / 2, CW - wi / 2)
        cyi = clamp(cyi, hi / 2, CH - hi / 2)
        patch = plane.crop((_int(cxi - wi / 2), _int(cyi - hi / 2), _int(cxi + wi / 2), _int(cyi + hi / 2))).resize((W, H))
        out = Image.alpha_composite(out, patch.convert("RGBA"))
    if char_layer is not None:
        pf = PARALLAX[1]
        cxi = cx + (cx - CW / 2) * pf * max(zoom, 0.0) * 1.6
        cyi = cy + (cy - CH / 2) * pf * max(zoom, 0.0) * 1.6
        wi = ww * (1 - (pf - 0.8) * zoom * 0.55)
        hi = wh * (1 - (pf - 0.8) * zoom * 0.55)
        cxi = clamp(cxi, wi / 2, CW - wi / 2)
        cyi = clamp(cyi, hi / 2, CH - hi / 2)
        patch = char_layer.crop((_int(cxi - wi / 2), _int(cyi - hi / 2), _int(cxi + wi / 2), _int(cyi + hi / 2))).resize((W, H))
        out = Image.alpha_composite(out, patch)
    if vfx is not None:
        out = Image.alpha_composite(out, vfx)
    return out


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


def draw_character(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    scale: float,
    colors: list[str],
    t: float,
    talk: float = 0.0,
    blink: bool = False,
) -> None:
    """Simple stylized presenter figure (head + torso + arms) with real life:
    breathing bob, speech-driven mouth + gestures, periodic blinks."""
    bob = math.sin(t * 2.2) * 1.5 * scale
    skin, shirt = (232, 190, 160), colors[0] if colors else (245, 179, 1)
    head_r = 16 * scale
    hy = cy - 34 * scale + bob * 0.4
    draw.ellipse([_int(cx - head_r), _int(hy - head_r), _int(cx + head_r), _int(hy + head_r)], fill=skin)
    draw.ellipse([_int(cx - head_r * 0.85), _int(hy - head_r * 0.85), _int(cx + head_r * 0.85), _int(hy + head_r * 0.85)], outline=(40, 30, 24), width=1)
    # eyes (blink = thin closed line)
    eye_y = hy + head_r * 0.18
    for side in (-1, 1):
        ex = cx + side * head_r * 0.42
        if blink:
            draw.line([_int(ex - 3.6 * scale), _int(eye_y), _int(ex + 3.6 * scale), _int(eye_y)], fill=(40, 30, 24), width=2)
        else:
            draw.ellipse([_int(ex - 3.4 * scale), _int(eye_y - 3.4 * scale), _int(ex + 3.4 * scale), _int(eye_y + 3.4 * scale)], fill=(40, 30, 24))
            draw.ellipse([_int(ex - 1.4 * scale), _int(eye_y - 1.4 * scale), _int(ex + 1.4 * scale), _int(eye_y + 1.4 * scale)], fill=(255, 255, 250))
    # mouth — opens with the speech envelope
    mw = 4.2 * scale
    mh = 1.6 * scale + talk * 4.6 * scale
    draw.ellipse([_int(cx - mw), _int(hy + 8.5 * scale - mh / 2), _int(cx + mw), _int(hy + 8.5 * scale + mh / 2)], fill=(110, 38, 30))
    draw.rounded_rectangle([_int(cx - 22 * scale), _int(hy + 6 * scale), _int(cx + 22 * scale), _int(hy + 58 * scale)], _int(10 * scale), fill=shirt)
    for side in (-1, 1):  # arms — speech gestures + idle sway
        ax = cx + side * 22 * scale
        lift = math.sin(t * 1.6 + side) * 6 * scale + (talk * 0.6) * math.sin(t * 4.4 + side * 2.2) * 9 * scale
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
        noise = Image.effect_noise(frame.size, 22).convert("L")
        noise = Image.merge("RGB", (noise, noise, noise)).filter(ImageFilter.GaussianBlur(0.5))
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


# ----------------------------------------------------------------- hybrid
def _still_planes(img: Image.Image, canvas: tuple[int, int], rng: random.Random) -> tuple[Image.Image, Image.Image, Image.Image]:
    """Depth planes carved from one photoreal still: far is a re-blurred,
    darkened witness plane (aerial perspective), mid holds the sharp main
    action plane, near is the foreground buffer the camera sweeps past."""
    cw, ch = canvas
    far_w = max(64, int(cw * 0.55))
    far = img.resize((far_w, int(ch * far_w / cw)), Image.LANCZOS).resize((cw, ch), Image.BILINEAR)
    far = far.filter(ImageFilter.GaussianBlur(1.8))
    far = ImageEnhance.Brightness(far).enhance(0.88)
    far = ImageEnhance.Color(far).enhance(0.90)
    far = ImageEnhance.Contrast(far).enhance(0.96)

    mid = cover_fit(img, canvas)
    mid = ImageEnhance.Sharpness(mid).enhance(1.18)
    mid = ImageEnhance.Contrast(mid).enhance(1.04)

    near = cover_fit(img, canvas)
    near = ImageEnhance.Brightness(near).enhance(0.92)
    near = near.filter(ImageFilter.GaussianBlur(0.6))
    near_pad = Image.new("RGB", (cw, ch), (10, 10, 14))
    near = Image.blend(near, near_pad, 0.08)  # keeps near from stealing focus
    return far, mid, near


def make_planes(spec: dict, canvas: tuple[int, int], rng: random.Random) -> tuple:
    """Hybrid: photoreal stills when the free rail is up, painted planes
    otherwise. Returns (far, mid, near, still_meta)."""
    from .stills import fetch_still, get_still_prompt

    still = None
    still_prompt = get_still_prompt(spec)
    try:
        still = fetch_still(still_prompt, spec.get("seed", 7), canvas[0], canvas[1])
    except Exception as exc:  # noqa: BLE001
        log.warning("still fetch crashed (%s) — painted planes", exc)
    if still is not None:
        return (*_still_planes(still, canvas, rng), {"still": True, "still_model": "flux", "still_prompt": still_prompt})
    far = paint_far(canvas, spec.get("environment_category", "generic"), spec.get("palette") or ["#2b2b33", "#4a4a55", "#f5b301"], rng)
    mid = paint_mid(canvas, spec.get("environment_category", "generic"), spec.get("palette") or ["#2b2b33", "#4a4a55", "#f5b301"], rng)
    near = paint_near(canvas, spec.get("environment_category", "generic"), spec.get("palette") or ["#2b2b33", "#4a4a55", "#f5b301"], rng)
    return far, mid, near, {"still": False}


# ----------------------------------------------------------------- render
def render_clip(spec: dict, out_dir: Path | None = None) -> dict:
    """Render one clip → mp4 (+ thumbnail jpg). Returns file metadata.

    2.5D pipeline: the environment is painted once as three depth planes
    (far / mid / near) and the camera animates a parallax window across them,
    so pans, trucks and push-ins reveal real depth separation — all keyless.
    """
    import time as _time

    rng = random.Random(spec.get("seed", 7) ^ hash(spec.get("clip_id", "clip")) & 0xFFFFFFFF)
    W = int(spec.get("width", 480))
    H = int(spec.get("height", 270))
    fps = int(spec.get("fps", 18))
    dur = clamp(float(spec.get("duration_s", 3.5)), 0.8, 8.0)
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
    canvas = (int(W * S_CANVAS), int(H * S_CANVAS))

    # depth planes built once (parallax done at crop time) — photoreal
    # stills when reachable, painted planes offline
    far, mid, near, still_meta = make_planes(spec, canvas, rng)

    # character acting: blink rhythm + speech envelope for narrator beats
    blink_period = 2.6 + rng.uniform(0.0, 2.2)
    spoken_beat = (char.get("action", "") + " " + str(move)).lower() if char else ""
    speaks = any(k in spoken_beat for k in ("narrat", "speak", "talk", "line", "voice", "deliver", "present", "to camera"))

    # overlays live in output space (drawn once, composited per frame).
    # Photoreal planes arrive already graded + lit by the diffusion model —
    # heavy overlays would crush their dynamic range, so dial them back.
    photo = bool(still_meta.get("still", False))
    # composition bias: keep the subject-dense midground in frame during
    # pushes/trucks (photoreal stills carry their weight lower than painted
    # skies) — a real framing choice, not a hack.
    frame_bias_y = 1.10 if photo else 1.0
    light_static = lighting_overlay((W, H), lighting, tod, rng)
    vig = vignette((W, H))
    if photo:
        light_static.putalpha(light_static.getchannel("A").point(lambda a: int(a * 0.55)))
        vig.putalpha(vig.getchannel("A").point(lambda a: int(a * 0.60)))
    tint_alpha = 13 if photo else 26

    tmp = Path(tempfile.mkdtemp(prefix="cfframes_"))
    t0 = _time.time()
    try:
        for i in range(n):
            t = i / fps
            cam = camera_window(move, t, dur, W, H, rng)
            if frame_bias_y != 1.0:
                cx0, cy0, zoom, rot, p = cam
                cam = (cx0, min(H * S_CANVAS - H * (1 + zoom) / 2, cy0 * frame_bias_y), zoom, rot, p)
            char_layer = None
            if char:
                char_layer = Image.new("RGBA", canvas, (0, 0, 0, 0))
                pos = char.get("position", "center")
                fcx = {"left third": 0.26, "center": 0.5, "right third": 0.74}.get(pos, 0.5) * canvas[0]
                fcy = canvas[1] * 0.42
                scale = 1.35 * (1 + 0.12 * (t / dur) if "toward" in char.get("action", "") else 1)
                talk = max(0.0, 0.55 + 0.45 * math.sin(t * 11.3) * math.sin(t * 4.1)) if speaks else 0.0
                draw_character(
                    ImageDraw.Draw(char_layer), fcx, fcy, scale, char.get("palette", palette), t,
                    talk=talk, blink=(t % blink_period) < 0.13,
                )
            vfx = Image.alpha_composite(
                atmosphere((W, H), cat, t, rng, weather=str(spec.get("weather", "")), tod=tod, mood=mood),
                env_anim((W, H), cat, t, rng),
            )
            frame: Image.Image = compose_2d5(far, mid, near, W, H, cam, char_layer, vfx)
            _, _, _, rot, _ = cam
            if rot:
                frame = frame.rotate(-rot, resample=Image.BICUBIC, expand=True)
                frame = frame.resize((W, H))

            frame = Image.alpha_composite(frame, light_static)
            tint = MOOD_TINTS.get(mood)
            if tint:
                tint_layer = Image.new("RGBA", (W, H), tint + (tint_alpha,))
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
        "provider_meta": {
            "source": "procedural-2.5d" if not still_meta["still"] else "photoreal-hybrid",
            "grade": STYLE_GRADES.get(style, STYLE_GRADES["kling-3.0"])["grade"],
            "parallax": list(PARALLAX),
            "movement": move,
            **still_meta,
            "rendered_in_s": round(_time.time() - t0, 1),
        },
    }
