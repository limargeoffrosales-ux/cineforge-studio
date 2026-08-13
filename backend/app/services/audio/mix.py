"""Soundtrack mixer — builds the full-film audio track.

Consumes the pipeline's music / sound_design / voice_generation outputs,
aligns every layer to the global timeline (same offsets as the video
assembly), ducks the music under narration, applies a master limiter and
writes a stereo WAV for the ffmpeg mux.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from ...models import Project, VideoClip
from ...config import settings
from .synth import SR, ambience, impact, music_bed, normalize, riser, soft_limit, whoosh, write_wav
from .providers import synthesize

log = logging.getLogger("cineforge.audio.mix")

FADE = 0.5  # must match render._stitch crossfade
DUCK_GAIN = 0.55  # music level while narration is speaking


def scene_offsets(clips: list[VideoClip]) -> dict[str, float]:
    """scene_id → global start time, mirroring the video assembly math."""
    offsets: dict[str, float] = {}
    seen: set[str] = set()
    acc = 0.0
    for clip in clips:
        if clip.scene_id not in seen:
            offsets[clip.scene_id] = acc
            seen.add(clip.scene_id)
        acc += clip.duration_s
    return offsets


def build_soundtrack(project: Project, clips: list[VideoClip], out_path: Path, owner_id: str | None = None) -> dict | None:
    """Mix the film's soundtrack; returns a report dict or None on failure."""
    try:
        if not clips:
            return None
        music = project.outputs.get("music") or {}
        sound = project.outputs.get("sound_design") or {}
        voice = project.outputs.get("voice_generation") or {}
        offsets = scene_offsets(clips)
        total = max(1.0, sum(c.duration_s for c in clips) + 0.6)

        n = int(total * SR)
        bus = np.zeros((n, 2), dtype=np.float32)
        duck_region = np.zeros(n, dtype=np.float32)
        tracks: list[dict] = []

        # ------------------------------------------------------------ music
        for scene in project.outputs.get("script", {}).get("scenes", []):
            sid = scene["id"]
            off = offsets.get(sid)
            if off is None:
                continue
            dur = min(scene.get("duration", 4.0), total - off)
            if dur <= 0.2:
                continue
            plan = next((t for t in (music.get("tracks") or []) if t.get("scene_id") == sid), None)
            genre = (plan or {}).get("genre", "cinematic orchestral")
            mood = (plan or {}).get("mood", "cinematic")
            bpm = (plan or {}).get("bpm")
            key = (plan or {}).get("key", "C major")
            bed = music_bed(genre, mood, bpm, key, dur, rng_seed=int(sid.split("-")[-1] or 1) + 7)
            i0 = int(off * SR)
            bed2 = np.stack([bed, bed], axis=-1)
            bus[i0 : i0 + len(bed2)] += bed2
            tracks.append({"kind": "music", "scene": sid, "genre": genre, "mood": mood, "bpm": bpm, "key": key, "at": round(off, 2), "dur": round(dur, 2)})

        # ------------------------------------------- ambience + sfx layers
        for s in (sound.get("ambience") or []):
            sid = s.get("scene_id")
            off = offsets.get(sid)
            if off is None:
                continue
            dur = min(12.0, total - off)
            bed = ambience(s.get("bed", "room tone"), dur, amp=0.12)
            i0 = int(off * SR)
            a2 = np.stack([bed, bed], axis=-1)
            bus[i0 : i0 + len(a2)] += a2
            tracks.append({"kind": "ambience", "scene": sid, "bed": s.get("bed")})

        for s in (sound.get("sfx") or []):
            sid = s.get("scene_id")
            off = offsets.get(sid)
            if off is None:
                continue
            cue = (s.get("cue") or "").lower()
            dur = min(2.2, total - off)
            if "riser" in cue:
                fx = riser(dur, amp=0.16)
            elif "impact" in cue or "hit" in cue or "drop" in cue:
                fx = impact(dur, amp=0.4)
            elif "swell" in cue or "sweep" in cue or "whoosh" in cue:
                fx = whoosh(dur, amp=0.16)
            else:
                fx = impact(min(0.5, dur), amp=0.18)
            i0 = int(off * SR)
            f2 = np.stack([fx, fx], axis=-1)
            bus[i0 : i0 + len(f2)] += f2
            tracks.append({"kind": "sfx", "scene": sid, "cue": s.get("cue")})

        # -------------------------------------------------------- narration
        narration_count = 0
        narration_provider = None
        narration_voice = None
        for line in (voice.get("narration_tracks") or []):
            sid = line.get("scene_id")
            off = offsets.get(sid)
            if off is None:
                continue
            start = off + float(line.get("start", 0))
            end = off + float(line.get("end", start + 2))
            dur = max(0.8, end - start)
            text = line.get("text", "")
            char_voice = voice.get("voices") or []
            v = next((x for x in char_voice if x.get("character") == line.get("speaker")), None)
            voice_id = ((v or {}).get("profile") or {}).get("style", "nova")
            # emotion-aware voice mapping
            emotion = (line.get("emotion") or "neutral")
            if voice_id == "nova" and emotion == "passionate":
                voice_id = "shimmer"
            result = synthesize(text, voice_id, provider=settings.AUDIO_DEFAULTS.get("tts_provider", "edge"), owner_id=owner_id)
            if result:
                audio = result["audio"]
                i0 = int(start * SR)
                seg = audio[: int(dur * SR)]
                if len(seg) < int(0.15 * SR):
                    seg = np.pad(seg, (0, int(0.15 * SR) - len(seg)))
                seg2 = np.stack([seg, seg], axis=-1)
                bus[i0 : i0 + len(seg2)] += seg2 * 0.95
                duck_region[i0 : min(n, i0 + len(seg2))] = 1.0
                narration_count += 1
                narration_provider = result.get("provider", narration_provider)
                narration_voice = result.get("voice", narration_voice)
                tracks.append({"kind": "narration", "scene": sid, "speaker": line.get("speaker"), "text": text[:70]})

        # ------------------------------------------------------------- mix
        # music ducking under narration
        if narration_count:
            k = int(0.15 * SR)  # smoothing kernel
            smooth = np.convolve(duck_region, np.ones(k) / k, mode="same")
            gain = 1.0 - (1.0 - DUCK_GAIN) * smooth
            bus *= gain[:, None]
            # voice bed slightly louder after ducking
        bus = soft_limit(bus, 1.25)
        bus = normalize(bus, 0.89)
        # master fade in/out
        fade_in = int(0.5 * SR)
        fade_out = int(1.2 * SR)
        bus[:fade_in] *= np.linspace(0, 1, fade_in)[:, None]
        bus[-fade_out:] *= np.linspace(1, 0, fade_out)[:, None]

        write_wav(out_path, bus)
        return {
            "tracks": tracks,
            "music_scenes": sum(1 for t in tracks if t["kind"] == "music"),
            "sfx_count": sum(1 for t in tracks if t["kind"] == "sfx"),
            "narration_lines": narration_count,
            "narration_provider": narration_provider,
            "narration_voice": narration_voice,
            "duration_s": round(total, 2),
            "mixed": True,
            "mock_narration": narration_count == 0,
        }
    except Exception as exc:  # noqa: BLE001
        log.exception("soundtrack build failed")
        return {"mixed": False, "error": str(exc)[:200]}
