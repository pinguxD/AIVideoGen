from __future__ import annotations

import json
import math
import shutil
import subprocess
import tempfile
import wave
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parents[1]
REFERENCE_DIR = BASE / "assets" / "reference_videos"
MEME_TEMPLATE_DIR = BASE / "assets" / "meme_templates"
SOUND_DIR = BASE / "assets" / "sounds"
ANALYSIS_DIR = BASE / "outputs" / "reference_analysis"

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".flac"}


@dataclass
class Scene:
    start: float
    end: float
    duration: float
    change_score: float
    motion_score: float
    text_density: float
    insert_probability: float


@dataclass
class AudioEvent:
    start: float
    end: float
    peak_db: float
    kind: str


@dataclass
class VideoAnalysis:
    source_file: str
    duration: float
    width: int
    height: int
    fps: float
    title_hint: str = ""
    scenes: list[Scene] = field(default_factory=list)
    audio_events: list[AudioEvent] = field(default_factory=list)
    speech_ratio: float = 0.0
    silence_ratio: float = 0.0
    probable_voiceover: bool = False
    probable_synthetic_voice: bool = False
    synthetic_voice_confidence: int = 0
    meme_template_matches: list[dict[str, Any]] = field(default_factory=list)
    local_sound_matches: list[dict[str, Any]] = field(default_factory=list)
    visual_structure: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def save(self) -> Path:
        ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(
            ch if ch.isalnum() or ch in "-_" else "_"
            for ch in Path(self.source_file).stem
        )
        path = ANALYSIS_DIR / f"{safe_name}.analysis.json"
        path.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path


def ensure_directories() -> None:
    for directory in (
        REFERENCE_DIR,
        MEME_TEMPLATE_DIR,
        SOUND_DIR,
        ANALYSIS_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def _require_binary(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(
            f"{name} was not found on PATH. Install FFmpeg and restart the terminal."
        )
    return path


def _run_json(command: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def probe_video(path: Path) -> dict[str, Any]:
    ffprobe = _require_binary("ffprobe")
    data = _run_json(
        [
            ffprobe,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ]
    )

    video_stream = next(
        (
            stream
            for stream in data.get("streams", [])
            if stream.get("codec_type") == "video"
        ),
        {},
    )

    rate = str(
        video_stream.get("avg_frame_rate")
        or video_stream.get("r_frame_rate")
        or "0/1"
    )
    try:
        numerator, denominator = rate.split("/", 1)
        fps = float(numerator) / max(float(denominator), 1.0)
    except Exception:
        fps = 0.0

    duration = float(
        video_stream.get("duration")
        or data.get("format", {}).get("duration")
        or 0.0
    )

    return {
        "duration": duration,
        "width": int(video_stream.get("width") or 0),
        "height": int(video_stream.get("height") or 0),
        "fps": fps,
    }


def _frame_metrics(frame: np.ndarray, previous: np.ndarray | None) -> dict[str, float]:
    import cv2

    small = cv2.resize(frame, (224, 224), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

    hist = cv2.calcHist([gray], [0], None, [64], [0, 256])
    cv2.normalize(hist, hist)

    change_score = 0.0
    motion_score = 0.0

    if previous is not None:
        previous_small = cv2.resize(
            previous,
            (224, 224),
            interpolation=cv2.INTER_AREA,
        )
        previous_gray = cv2.cvtColor(previous_small, cv2.COLOR_BGR2GRAY)
        previous_hist = cv2.calcHist(
            [previous_gray],
            [0],
            None,
            [64],
            [0, 256],
        )
        cv2.normalize(previous_hist, previous_hist)

        correlation = cv2.compareHist(
            hist,
            previous_hist,
            cv2.HISTCMP_CORREL,
        )
        change_score = max(0.0, min(1.0, 1.0 - correlation))
        motion_score = float(
            np.mean(
                np.abs(
                    gray.astype(np.float32)
                    - previous_gray.astype(np.float32)
                )
            )
            / 255.0
        )

    edges = cv2.Canny(gray, 80, 180)
    edge_ratio = float(np.mean(edges > 0))

    # Text-like areas are estimated from many small high-contrast contours.
    contours, _ = cv2.findContours(
        edges,
        cv2.RETR_LIST,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    text_like = 0
    central_large_rectangles = 0

    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        area = width * height

        if 8 <= width <= 90 and 4 <= height <= 32 and area <= 1800:
            text_like += 1

        if (
            width >= 70
            and height >= 70
            and x > 15
            and y > 15
            and x + width < 209
            and y + height < 209
        ):
            central_large_rectangles += 1

    text_density = min(1.0, text_like / 180.0)
    insert_probability = min(
        1.0,
        central_large_rectangles / 12.0 + max(0.0, edge_ratio - 0.12) * 2.5,
    )

    return {
        "change_score": change_score,
        "motion_score": motion_score,
        "text_density": text_density,
        "insert_probability": insert_probability,
    }


def analyze_frames(
    path: Path,
    duration: float,
    sample_interval: float = 0.5,
) -> tuple[list[Scene], dict[str, Any], list[np.ndarray]]:
    import cv2

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"OpenCV could not open {path}")

    samples: list[dict[str, float]] = []
    sample_frames: list[np.ndarray] = []
    previous = None
    time_position = 0.0

    while time_position < duration:
        capture.set(cv2.CAP_PROP_POS_MSEC, time_position * 1000.0)
        ok, frame = capture.read()
        if not ok:
            time_position += sample_interval
            continue

        metrics = _frame_metrics(frame, previous)
        samples.append({"time": time_position, **metrics})

        if len(sample_frames) < 30:
            sample_frames.append(frame.copy())
        elif int(time_position / sample_interval) % max(
            1,
            int(duration / sample_interval / 30),
        ) == 0:
            sample_frames.append(frame.copy())

        previous = frame
        time_position += sample_interval

    capture.release()

    if not samples:
        return [], {}, []

    threshold = max(
        0.16,
        float(np.percentile([item["change_score"] for item in samples], 88)),
    )

    boundaries = [0.0]
    for item in samples:
        if item["change_score"] >= threshold:
            if item["time"] - boundaries[-1] >= 0.7:
                boundaries.append(item["time"])

    if duration - boundaries[-1] >= 0.4:
        boundaries.append(duration)
    elif boundaries[-1] != duration:
        boundaries[-1] = duration

    scenes: list[Scene] = []

    for index in range(len(boundaries) - 1):
        start = boundaries[index]
        end = boundaries[index + 1]
        relevant = [
            item
            for item in samples
            if start <= item["time"] < end
        ]
        if not relevant:
            continue

        scenes.append(
            Scene(
                start=round(start, 3),
                end=round(end, 3),
                duration=round(end - start, 3),
                change_score=round(
                    float(np.mean([item["change_score"] for item in relevant])),
                    4,
                ),
                motion_score=round(
                    float(np.mean([item["motion_score"] for item in relevant])),
                    4,
                ),
                text_density=round(
                    float(np.mean([item["text_density"] for item in relevant])),
                    4,
                ),
                insert_probability=round(
                    float(
                        np.mean(
                            [item["insert_probability"] for item in relevant]
                        )
                    ),
                    4,
                ),
            )
        )

    visual_structure = {
        "scene_count": len(scenes),
        "average_scene_length": round(
            float(np.mean([scene.duration for scene in scenes])),
            3,
        )
        if scenes
        else duration,
        "cuts_per_10_seconds": round(
            len(scenes) / max(duration, 0.1) * 10,
            2,
        ),
        "average_motion": round(
            float(np.mean([item["motion_score"] for item in samples])),
            4,
        ),
        "average_text_density": round(
            float(np.mean([item["text_density"] for item in samples])),
            4,
        ),
        "visual_insert_ratio": round(
            float(
                np.mean(
                    [
                        item["insert_probability"] >= 0.48
                        for item in samples
                    ]
                )
            ),
            4,
        ),
        "continuous_background_likely": len(scenes) <= max(
            3,
            int(duration / 5),
        ),
    }

    return scenes, visual_structure, sample_frames


def extract_audio_wav(path: Path, output: Path) -> bool:
    ffmpeg = _require_binary("ffmpeg")
    result = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and output.exists()


def _read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as wav:
        sample_rate = wav.getframerate()
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        frames = wav.readframes(wav.getnframes())

    if sample_width != 2:
        raise RuntimeError("Only 16-bit PCM WAV is supported")

    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    audio /= 32768.0
    return audio, sample_rate


def _db(value: float) -> float:
    return 20.0 * math.log10(max(value, 1e-8))


def analyze_audio(path: Path) -> tuple[
    list[AudioEvent],
    float,
    float,
    bool,
    bool,
    int,
]:
    with tempfile.TemporaryDirectory(prefix="trend_radar_audio_") as temp:
        wav_path = Path(temp) / "reference.wav"
        if not extract_audio_wav(path, wav_path):
            return [], 0.0, 1.0, False, False, 0

        audio, sample_rate = _read_wav(wav_path)

    window_seconds = 0.25
    window_size = max(1, int(sample_rate * window_seconds))
    rms_values: list[float] = []
    zero_crossings: list[float] = []

    for start in range(0, len(audio), window_size):
        chunk = audio[start : start + window_size]
        if len(chunk) == 0:
            continue
        rms_values.append(float(np.sqrt(np.mean(chunk**2))))
        zero_crossings.append(
            float(np.mean(np.abs(np.diff(np.signbit(chunk)).astype(np.float32))))
        )

    if not rms_values:
        return [], 0.0, 1.0, False, False, 0

    rms = np.asarray(rms_values)
    zcr = np.asarray(zero_crossings)

    silence_threshold = max(0.004, float(np.percentile(rms, 20)) * 1.3)
    active = rms > silence_threshold
    silence_ratio = float(np.mean(~active))

    # Speech proxy: active audio with moderate zero crossing and stable energy.
    speech_proxy = (
        active
        & (zcr >= 0.015)
        & (zcr <= 0.25)
        & (rms <= max(0.08, float(np.percentile(rms, 92))))
    )
    speech_ratio = float(np.mean(speech_proxy))
    probable_voiceover = speech_ratio >= 0.34

    events: list[AudioEvent] = []
    peak_threshold = max(
        float(np.percentile(rms, 90)),
        float(np.mean(rms) + np.std(rms) * 1.5),
    )
    in_event = False
    event_start = 0

    for index, value in enumerate(rms):
        is_peak = value >= peak_threshold
        if is_peak and not in_event:
            in_event = True
            event_start = index
        elif not is_peak and in_event:
            in_event = False
            start_time = event_start * window_seconds
            end_time = index * window_seconds
            peak = float(np.max(rms[event_start:index]))
            events.append(
                AudioEvent(
                    start=round(start_time, 3),
                    end=round(end_time, 3),
                    peak_db=round(_db(peak), 2),
                    kind="impact_or_sound_effect",
                )
            )

    # This is deliberately conservative. It is not proof of TTS.
    active_rms = rms[active]
    synthetic_confidence = 0
    probable_synthetic = False

    if probable_voiceover and len(active_rms) >= 8:
        coefficient_of_variation = float(
            np.std(active_rms) / max(np.mean(active_rms), 1e-8)
        )
        regularity = max(0.0, 1.0 - coefficient_of_variation)
        synthetic_confidence = int(
            max(0, min(65, round(regularity * 65)))
        )
        probable_synthetic = synthetic_confidence >= 52

    return (
        events,
        round(speech_ratio, 4),
        round(silence_ratio, 4),
        probable_voiceover,
        probable_synthetic,
        synthetic_confidence,
    )


def _average_hash(frame: np.ndarray, size: int = 16) -> np.ndarray:
    import cv2

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (size, size), interpolation=cv2.INTER_AREA)
    return resized > np.mean(resized)


def match_meme_templates(
    sample_frames: list[np.ndarray],
) -> list[dict[str, Any]]:
    import cv2

    templates = [
        path
        for path in MEME_TEMPLATE_DIR.rglob("*")
        if path.suffix.lower() in IMAGE_EXTENSIONS
    ]
    if not templates or not sample_frames:
        return []

    frame_hashes = [_average_hash(frame) for frame in sample_frames]
    matches: list[dict[str, Any]] = []

    for template in templates:
        image = cv2.imread(str(template))
        if image is None:
            continue
        template_hash = _average_hash(image)
        similarities = [
            1.0 - float(np.mean(frame_hash != template_hash))
            for frame_hash in frame_hashes
        ]
        best = max(similarities, default=0.0)
        if best >= 0.73:
            matches.append(
                {
                    "template": str(template.relative_to(BASE)).replace("\\", "/"),
                    "similarity": round(best, 4),
                }
            )

    return sorted(
        matches,
        key=lambda item: item["similarity"],
        reverse=True,
    )[:10]


def _audio_fingerprint(path: Path) -> np.ndarray | None:
    with tempfile.TemporaryDirectory(prefix="trend_radar_fp_") as temp:
        wav_path = Path(temp) / "audio.wav"
        if not extract_audio_wav(path, wav_path):
            return None
        audio, sample_rate = _read_wav(wav_path)

    if len(audio) < sample_rate // 2:
        return None

    max_samples = sample_rate * 8
    audio = audio[:max_samples]
    audio = audio - np.mean(audio)

    frame_size = 1024
    hop = 512
    spectra: list[np.ndarray] = []

    for start in range(0, len(audio) - frame_size, hop):
        frame = audio[start : start + frame_size]
        frame = frame * np.hanning(frame_size)
        spectrum = np.abs(np.fft.rfft(frame))
        bands = np.array_split(spectrum, 32)
        spectra.append(np.asarray([np.mean(band) for band in bands]))

    if not spectra:
        return None

    fingerprint = np.mean(np.asarray(spectra), axis=0)
    norm = float(np.linalg.norm(fingerprint))
    return fingerprint / norm if norm > 0 else fingerprint


def match_local_sounds(reference: Path) -> list[dict[str, Any]]:
    reference_fingerprint = _audio_fingerprint(reference)
    if reference_fingerprint is None:
        return []

    matches: list[dict[str, Any]] = []

    for sound in SOUND_DIR.rglob("*"):
        if sound.suffix.lower() not in AUDIO_EXTENSIONS:
            continue

        fingerprint = _audio_fingerprint(sound)
        if fingerprint is None:
            continue

        similarity = float(
            np.dot(reference_fingerprint, fingerprint)
            / max(
                np.linalg.norm(reference_fingerprint)
                * np.linalg.norm(fingerprint),
                1e-8,
            )
        )

        if similarity >= 0.78:
            matches.append(
                {
                    "sound": str(sound.relative_to(BASE)).replace("\\", "/"),
                    "similarity": round(similarity, 4),
                    "note": "whole-track spectral similarity; review manually",
                }
            )

    return sorted(
        matches,
        key=lambda item: item["similarity"],
        reverse=True,
    )[:10]


def analyze_reference_video(
    path: str | Path,
    title_hint: str = "",
    sample_interval: float = 0.5,
) -> VideoAnalysis:
    ensure_directories()
    source = Path(path)
    if not source.is_absolute():
        source = BASE / source
    if not source.exists():
        raise FileNotFoundError(source)
    if source.suffix.lower() not in VIDEO_EXTENSIONS:
        raise ValueError(f"Unsupported video type: {source.suffix}")

    metadata = probe_video(source)
    scenes, visual_structure, sample_frames = analyze_frames(
        source,
        metadata["duration"],
        sample_interval=sample_interval,
    )

    (
        audio_events,
        speech_ratio,
        silence_ratio,
        probable_voiceover,
        probable_synthetic_voice,
        synthetic_confidence,
    ) = analyze_audio(source)

    warnings: list[str] = []
    if probable_synthetic_voice:
        warnings.append(
            "Synthetic-voice detection is heuristic and must not be treated as proof."
        )
    if not sample_frames:
        warnings.append("No usable frames were sampled.")
    if metadata["duration"] > 90:
        warnings.append(
            "Long reference video: analysis may be slower and template extraction less precise."
        )

    analysis = VideoAnalysis(
        source_file=str(source.relative_to(BASE)).replace("\\", "/")
        if source.is_relative_to(BASE)
        else str(source),
        duration=round(metadata["duration"], 3),
        width=metadata["width"],
        height=metadata["height"],
        fps=round(metadata["fps"], 3),
        title_hint=title_hint,
        scenes=scenes,
        audio_events=audio_events,
        speech_ratio=speech_ratio,
        silence_ratio=silence_ratio,
        probable_voiceover=probable_voiceover,
        probable_synthetic_voice=probable_synthetic_voice,
        synthetic_voice_confidence=synthetic_confidence,
        meme_template_matches=match_meme_templates(sample_frames),
        local_sound_matches=match_local_sounds(source),
        visual_structure=visual_structure,
        warnings=warnings,
    )
    analysis.save()
    return analysis
