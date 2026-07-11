from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
import wave
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from .full_video_analyzer import BASE


@dataclass
class VoiceProfile:
    speech_present: bool
    estimated_wpm: int
    energy: str
    pacing: str
    pitch_band: str
    delivery: str
    tts_style: float
    tts_stability: float
    tts_similarity_boost: float
    search_terms: list[str]
    confidence: int

    def to_dict(self) -> dict:
        return asdict(self)


def _extract_audio(source: Path, target: Path) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg was not found on PATH.")
    result = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "22050",
            "-c:a",
            "pcm_s16le",
            str(target),
        ],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and target.exists()


def _read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as stream:
        rate = stream.getframerate()
        channels = stream.getnchannels()
        width = stream.getsampwidth()
        raw = stream.readframes(stream.getnframes())

    if width != 2:
        raise RuntimeError("Expected 16-bit PCM audio.")

    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    return audio, rate


def _estimate_pitch(audio: np.ndarray, sample_rate: int) -> float:
    if len(audio) < sample_rate // 2:
        return 0.0

    chunk = audio[: min(len(audio), sample_rate * 12)]
    chunk = chunk - float(np.mean(chunk))
    correlations = np.correlate(chunk, chunk, mode="full")[len(chunk) - 1 :]
    min_lag = max(1, int(sample_rate / 350))
    max_lag = min(len(correlations) - 1, int(sample_rate / 70))

    if max_lag <= min_lag:
        return 0.0

    region = correlations[min_lag:max_lag]
    lag = int(np.argmax(region)) + min_lag
    return float(sample_rate / lag) if lag > 0 else 0.0


def profile_voice(source_file: str | Path) -> VoiceProfile:
    source = Path(source_file)
    if not source.is_absolute():
        source = BASE / source
    if not source.exists():
        raise FileNotFoundError(source)

    with tempfile.TemporaryDirectory(prefix="voice_profile_") as temp:
        wav_path = Path(temp) / "voice.wav"
        if not _extract_audio(source, wav_path):
            return VoiceProfile(
                speech_present=False,
                estimated_wpm=0,
                energy="unknown",
                pacing="unknown",
                pitch_band="unknown",
                delivery="unknown",
                tts_style=0.15,
                tts_stability=0.50,
                tts_similarity_boost=0.75,
                search_terms=["clear narration"],
                confidence=20,
            )
        audio, rate = _read_wav(wav_path)

    window = max(1, int(rate * 0.20))
    rms_values = []
    zcr_values = []

    for start in range(0, len(audio), window):
        chunk = audio[start : start + window]
        if len(chunk) < window // 2:
            continue
        rms_values.append(float(np.sqrt(np.mean(chunk**2))))
        zcr_values.append(
            float(
                np.mean(
                    np.abs(
                        np.diff(np.signbit(chunk)).astype(np.float32)
                    )
                )
            )
        )

    if not rms_values:
        return VoiceProfile(
            speech_present=False,
            estimated_wpm=0,
            energy="unknown",
            pacing="unknown",
            pitch_band="unknown",
            delivery="unknown",
            tts_style=0.15,
            tts_stability=0.50,
            tts_similarity_boost=0.75,
            search_terms=["clear narration"],
            confidence=20,
        )

    rms = np.asarray(rms_values)
    zcr = np.asarray(zcr_values)
    active_threshold = max(0.004, float(np.percentile(rms, 22)) * 1.35)
    active = rms > active_threshold

    speech_like = active & (zcr >= 0.015) & (zcr <= 0.25)
    speech_ratio = float(np.mean(speech_like))
    speech_present = speech_ratio >= 0.25

    active_rms = rms[active] if np.any(active) else rms
    mean_energy = float(np.mean(active_rms))
    energy_variation = float(
        np.std(active_rms) / max(np.mean(active_rms), 1e-8)
    )

    if mean_energy >= 0.12:
        energy = "high"
    elif mean_energy >= 0.055:
        energy = "medium"
    else:
        energy = "low"

    # A heuristic cadence estimate based on energy changes. This is not
    # transcription-based WPM, but it is useful for TTS style selection.
    envelope_changes = np.abs(np.diff(rms))
    syllable_proxy = int(
        np.sum(
            envelope_changes
            > max(0.005, float(np.percentile(envelope_changes, 72)))
        )
    )
    duration_seconds = max(len(audio) / rate, 0.1)
    estimated_wpm = int(
        max(80, min(210, syllable_proxy / duration_seconds * 60 * 0.72))
    )

    if estimated_wpm >= 165:
        pacing = "fast"
    elif estimated_wpm >= 125:
        pacing = "medium"
    else:
        pacing = "slow"

    pitch_hz = _estimate_pitch(audio, rate)
    if pitch_hz >= 190:
        pitch_band = "high"
    elif pitch_hz >= 120:
        pitch_band = "medium"
    elif pitch_hz > 0:
        pitch_band = "low"
    else:
        pitch_band = "unknown"

    if energy == "high" and energy_variation >= 0.55:
        delivery = "energetic"
    elif energy == "low":
        delivery = "calm"
    elif energy_variation >= 0.70:
        delivery = "dramatic"
    else:
        delivery = "conversational"

    style = {
        "energetic": 0.52,
        "dramatic": 0.46,
        "conversational": 0.25,
        "calm": 0.12,
    }[delivery]
    stability = {
        "energetic": 0.34,
        "dramatic": 0.39,
        "conversational": 0.48,
        "calm": 0.62,
    }[delivery]

    terms = [delivery, pacing, "narration"]
    if pitch_band != "unknown":
        terms.append(f"{pitch_band} pitch")

    confidence = int(
        max(
            25,
            min(
                88,
                45 + speech_ratio * 35 + min(duration_seconds, 20) / 20 * 8,
            ),
        )
    )

    return VoiceProfile(
        speech_present=speech_present,
        estimated_wpm=estimated_wpm,
        energy=energy,
        pacing=pacing,
        pitch_band=pitch_band,
        delivery=delivery,
        tts_style=round(style, 2),
        tts_stability=round(stability, 2),
        tts_similarity_boost=0.78,
        search_terms=terms,
        confidence=confidence,
    )
