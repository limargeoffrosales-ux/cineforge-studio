"""Procedural audio synthesizer — music beds, SFX, ambience.

Pure numpy synthesis (no model weights): chord pads, bass, arpeggios,
percussion, risers/impacts, and ambient noise beds. This powers the
offline soundtrack; with TTS keys configured, real narration is layered
on top (see providers.py + mix.py).
"""
from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np

SR = 44100
PI = np.pi

# ----------------------------------------------------------------- scales
NOTES = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
MAJOR = (0, 2, 4, 5, 7, 9, 11)
MINOR = (0, 2, 3, 5, 7, 8, 10)
CHORD_PROGS = {
    "major": [(0, 2, 4), (5, 7, 9), (3, 5, 7), (0, 2, 4)],          # I vi IV V
    "minor": [(0, 2, 4), (5, 7, 9), (3, 5, 7), (4, 6, 8)],          # i VI III VII
}


def midi_to_freq(m: int) -> float:
    return 440.0 * (2 ** ((m - 69) / 12))


def _env(n: int, attack: float, release: float, sr: int = SR) -> np.ndarray:
    e = np.ones(n)
    a = min(max(1, int(attack * sr)), n)
    r = min(max(1, int(release * sr)), n)
    e[:a] = np.linspace(0, 1, a)
    e[-r:] = np.linspace(1, 0, r)
    return e


def tone(freq: float, dur: float, amp: float = 0.3, attack: float = 0.01, release: float = 0.08, detune: float = 0.0, sr: int = SR) -> np.ndarray:
    n = int(dur * sr)
    t = np.arange(n) / sr
    f = freq * (1 + detune)
    return (amp * _env(n, attack, release) * np.sin(2 * PI * f * t)).astype(np.float32)


def noise(dur: float, amp: float = 0.3, attack: float = 0.005, release: float = 0.05, sr: int = SR) -> np.ndarray:
    n = int(dur * sr)
    rng = np.random.default_rng(int(dur * 1000))
    return (amp * _env(n, attack, release) * rng.standard_normal(n)).astype(np.float32)


def lowpass(x: np.ndarray, cutoff: float, sr: int = SR) -> np.ndarray:
    """One-pole lowpass — cheap and good enough for beds."""
    rc = 1.0 / (2 * PI * cutoff)
    dt = 1.0 / sr
    a = dt / (rc + dt)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += a * (x[i] - acc)
        y[i] = acc
    return y


def _chord_notes(root_midi: int, scale: tuple, degs: tuple, octave: int = 0) -> list[int]:
    """Scale degrees → midi notes, wrapping octaves (e.g. deg 7 → root+12)."""
    out = []
    for d in degs:
        scale_deg = scale[d % len(scale)]
        oct_shift = d // len(scale)
        out.append(root_midi + scale_deg + 12 * (octave + oct_shift))
    return out


# ------------------------------------------------------------- instruments
def pad(freqs: list[float], dur: float, amp: float = 0.16) -> np.ndarray:
    n = int(dur * SR)
    out = np.zeros(n, dtype=np.float32)
    for f in freqs:
        out += tone(f, dur, amp=amp / len(freqs), attack=0.6, release=0.9, detune=0.0012)
    return out


def bass_note(freq: float, dur: float, amp: float = 0.26) -> np.ndarray:
    return lowpass(tone(freq, dur, amp=amp, attack=0.01, release=0.1), 320)


def pluck(freq: float, dur: float, amp: float = 0.22) -> np.ndarray:
    """Arpeggio pluck with exponential decay."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    env = np.exp(-t * 5.5)
    body = np.sin(2 * PI * freq * t) + 0.4 * np.sin(2 * PI * freq * 2 * t)
    return (amp * env * body).astype(np.float32)


def kick(dur: float = 0.32, amp: float = 0.5) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    freq = 120 * np.exp(-t * 18) + 44
    phase = 2 * PI * np.cumsum(freq) / SR
    return (amp * np.exp(-t * 12) * np.sin(phase)).astype(np.float32)


def snare(dur: float = 0.18, amp: float = 0.28) -> np.ndarray:
    return lowpass(noise(dur, amp=amp, attack=0.001, release=0.05), 5200)


def hat(dur: float = 0.06, amp: float = 0.12) -> np.ndarray:
    return highpassish(noise(dur, amp=amp, attack=0.001, release=0.02), 7000)


def highpassish(x: np.ndarray, cutoff: float, sr: int = SR) -> np.ndarray:
    return x - lowpass(x, cutoff, sr)


def riser(dur: float = 1.6, amp: float = 0.2) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    env = np.linspace(0, 1, n) ** 2
    sweep = np.sin(2 * PI * (120 + 900 * (t / dur)) * t)
    return ((env * sweep * 0.5) + (env * lowpass(noise(dur, 0.5), 900)) * 0.5).astype(np.float32)


def impact(dur: float = 0.5, amp: float = 0.55) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    thump = np.exp(-t * 16) * np.sin(2 * PI * 55 * t)
    burst = lowpass(noise(dur, amp=0.5, attack=0.001, release=0.1), 2600) * np.exp(-t * 10)
    return ((thump * 0.6 + burst * 0.5) * amp).astype(np.float32)


def whoosh(dur: float = 0.9, amp: float = 0.22) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    env = np.sin(np.linspace(0, PI, n)) ** 2
    sweep = lowpass(noise(dur, 0.6), 2400) * (0.4 + 0.6 * (t / dur))
    return (amp * env * sweep).astype(np.float32)


# -------------------------------------------------------------- ambience
def ambience(kind: str, dur: float, amp: float = 0.14) -> np.ndarray:
    kind = (kind or "room tone").lower()
    n = int(dur * SR)
    rng = np.random.default_rng(7)
    base = rng.standard_normal(n)
    t = np.arange(n) / SR
    if "ocean" in kind or "sea" in kind or "beach" in kind:
        lfo = 0.5 + 0.5 * np.sin(2 * PI * 0.12 * t + 1.4)
        out = lowpass(base, 600) * lfo
    elif "city" in kind or "traffic" in kind or "crowd" in kind:
        out = lowpass(base, 900) * (0.7 + 0.3 * np.sin(2 * PI * 0.4 * t))
    elif "forest" in kind or "wind" in kind or "nature" in kind:
        out = lowpass(base, 700) * (0.6 + 0.4 * np.sin(2 * PI * 0.22 * t + 0.5))
    elif "rain" in kind:
        out = highpassish(base, 1800) * 0.6
    else:  # room tone
        out = lowpass(base, 240) * 0.7
    fade = np.minimum(np.linspace(0, 1, n), np.linspace(1, 0, n))
    return (amp * out * fade).astype(np.float32)


# -------------------------------------------------------------- music bed
GENRE_PROFILES = {
    "cinematic orchestral": {"scale": "minor", "bpm_range": (70, 96), "layers": ("pads", "bass", "strings_swell"), "perc": "none"},
    "ambient electronic": {"scale": "minor", "bpm_range": (70, 84), "layers": ("pads", "bass"), "perc": "none"},
    "acoustic folk": {"scale": "major", "bpm_range": (84, 110), "layers": ("arpeggio", "bass"), "perc": "light"},
    "neon synthwave": {"scale": "minor", "bpm_range": (96, 110), "layers": ("pads", "bass", "arpeggio"), "perc": "full"},
    "uplifting": {"scale": "major", "bpm_range": (96, 120), "layers": ("pads", "bass", "arpeggio"), "perc": "light"},
    "tense": {"scale": "minor", "bpm_range": (60, 80), "layers": ("pads", "bass"), "perc": "none"},
    "gentle resolve": {"scale": "major", "bpm_range": (60, 80), "layers": ("pads",), "perc": "none"},
    "building": {"scale": "minor", "bpm_range": (80, 100), "layers": ("pads", "bass", "arpeggio"), "perc": "light"},
    "introspective": {"scale": "minor", "bpm_range": (60, 80), "layers": ("pads", "bass"), "perc": "none"},
    "triumphant": {"scale": "major", "bpm_range": (96, 120), "layers": ("pads", "bass", "arpeggio"), "perc": "full"},
}

SCALE_TONES = {"major": MAJOR, "minor": MINOR}
PROG_KEYS = {"major": CHORD_PROGS["major"], "minor": CHORD_PROGS["minor"]}
ROOT_MIDI = {"C": 48, "C#": 48, "D": 50, "D#": 50, "E": 52, "F": 53, "F#": 53, "G": 55, "G#": 55, "A": 57, "A#": 57, "B": 59}


def music_bed(genre: str, mood: str, bpm: int | None, key: str, dur: float, amp: float = 0.5, rng_seed: int = 1) -> np.ndarray:
    """Full music bed for a scene, length `dur` seconds."""
    genre = (genre or "cinematic orchestral").lower()
    prof = GENRE_PROFILES.get(genre, GENRE_PROFILES["cinematic orchestral"])
    if not bpm:
        lo, hi = prof["bpm_range"]
        bpm = int(lo + (hi - lo) * ((rng_seed % 10) / 10))
    scale = SCALE_TONES[prof["scale"]]
    root = ROOT_MIDI.get((key or "C").split()[0], 48)
    beats = max(1, int(dur * bpm / 60))
    beat_len = 60 / bpm
    rng = np.random.default_rng(rng_seed)
    n_total = int(dur * SR)
    out = np.zeros(n_total, dtype=np.float32)

    prog = PROG_KEYS[prof["scale"]]
    layers = prof["layers"]

    for bar in range(beats // 4 + 1):
        degs = prog[bar % len(prog)]
        chord = [midi_to_freq(m) for m in _chord_notes(root, scale, degs)]
        bar_start = bar * 4 * beat_len
        bar_end = min(dur, bar_start + 4 * beat_len)
        bar_len = max(0.05, bar_end - bar_start)
        n0 = int(bar_start * SR)
        n1 = int(bar_end * SR)
        if n1 <= n0:
            continue
        span = n1 - n0

        if "pads" in layers:
            pad_amp = amp * (0.30 if "perc" != "none" else 0.42)
            seg = pad(chord, bar_len, amp=pad_amp)
            if len(seg) < span:
                seg = np.pad(seg, (0, span - len(seg)))
            seg = seg[:span]
            # slow swell envelope per bar
            env = 0.75 + 0.25 * np.sin(np.linspace(0, PI, span) + bar)
            out[n0:n1] += seg * env

        if "bass" in layers:
            b = bass_note(chord[0] / 2, bar_len, amp=amp * 0.34)
            if len(b) < span:
                b = np.pad(b, (0, span - len(b)))
            out[n0:n1] += b[:span]

        if "arpeggio" in layers:
            step = beat_len / 2
            k = 0
            t0 = 0.0
            while t0 < bar_len:
                note = chord[k % 3] * (2 if k % 2 else 1)
                seg = pluck(note, min(step * 1.8, bar_len - t0), amp=amp * 0.16)
                i_start = n0 + int(t0 * SR)
                seg_len = min(len(seg), n1 - i_start)
                if seg_len > 0:
                    out[i_start : i_start + seg_len] += seg[:seg_len]
                t0 += step
                k += 1

        # percussion
        if prof["perc"] == "full":
            for k in range(4):
                t0 = k * beat_len
                if t0 >= bar_len:
                    break
                i_start = n0 + int(t0 * SR)
                if k % 4 == 0:
                    seg = kick() * amp
                else:
                    seg = hat() * amp
                seg_len = min(len(seg), n1 - i_start)
                if seg_len > 0:
                    out[i_start : i_start + seg_len] += seg[:seg_len]
            # snare on 2 & 4
            for k in (1, 3):
                t0 = k * beat_len
                if t0 >= bar_len:
                    break
                i_start = n0 + int(t0 * SR)
                seg = snare() * amp * 0.6
                seg_len = min(len(seg), n1 - i_start)
                if seg_len > 0:
                    out[i_start : i_start + seg_len] += seg[:seg_len]
        elif prof["perc"] == "light":
            seg = kick() * amp * 0.5
            seg_len = min(len(seg), span)
            if seg_len > 0:
                out[n0 : n0 + seg_len] += seg[:seg_len]

    return out.astype(np.float32)


# ---------------------------------------------------------------- export
def write_wav(path: Path, audio: np.ndarray, sr: int = SR) -> None:
    """Mono or stereo float array → 16-bit WAV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if audio.ndim == 1:
        audio = np.stack([audio, audio], axis=-1)
    audio = np.clip(audio, -1.0, 1.0)
    pcm = (audio * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def normalize(x: np.ndarray, peak: float = 0.85) -> np.ndarray:
    m = np.max(np.abs(x)) or 1.0
    return (x / m * peak).astype(np.float32)


def soft_limit(x: np.ndarray, drive: float = 1.2) -> np.ndarray:
    return np.tanh(x * drive).astype(np.float32)
