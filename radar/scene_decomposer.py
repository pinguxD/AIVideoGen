from __future__ import annotations
import json, math, shutil, subprocess, tempfile, wave
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import numpy as np
from .full_video_analyzer import BASE, probe_video

OUT = BASE / "outputs" / "recreation_intelligence"
KEYFRAMES = OUT / "keyframes"

@dataclass
class Transition:
    time: float
    kind: str
    confidence: int
    evidence: dict[str, float] = field(default_factory=dict)

@dataclass
class SoundEvent:
    start: float
    end: float
    family: str
    confidence: int
    peak_db: float

@dataclass
class Scene:
    start: float
    end: float
    duration: float
    motion: float
    brightness: float
    text_density: float
    probable_insert: bool
    keyframe: str

@dataclass
class Decomposition:
    source_file: str
    duration: float
    width: int
    height: int
    fps: float
    scenes: list[Scene]
    transitions: list[Transition]
    sound_effects: list[SoundEvent]
    visual_events: list[dict[str, Any]]
    audio_layers: dict[str, Any]
    editing_summary: dict[str, Any]
    warnings: list[str]
    def save(self) -> Path:
        OUT.mkdir(parents=True, exist_ok=True)
        path = OUT / f"{safe(Path(self.source_file))}.decomposition.json"
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        return path

def safe(path: Path) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in path.stem).strip("_") or "reference"

def resolve(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else BASE / path

def features(frame, previous):
    import cv2
    small = cv2.resize(frame, (320, 180), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    brightness = float(np.mean(gray) / 255)
    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    edges = cv2.Canny(gray, 70, 180)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    text_like = large = 0
    for contour in contours:
        _, _, w, h = cv2.boundingRect(contour)
        area = w * h
        if 8 <= w <= 120 and 4 <= h <= 35 and area <= 2500:
            text_like += 1
        if w >= 75 and h >= 55 and area >= 6000:
            large += 1
    result = {
        "brightness": brightness,
        "blur": blur,
        "text_density": min(1.0, text_like / 230),
        "insert_score": min(1.0, large / 8 + max(0, float(np.mean(edges > 0)) - .1) * 2.1),
        "difference": 0.0,
        "hist_change": 0.0,
        "flow": 0.0,
        "hflow": 0.0,
        "vflow": 0.0,
    }
    if previous is None:
        return result
    psmall = cv2.resize(previous, (320, 180), interpolation=cv2.INTER_AREA)
    pgray = cv2.cvtColor(psmall, cv2.COLOR_BGR2GRAY)
    result["difference"] = float(np.mean(np.abs(gray.astype("float32") - pgray.astype("float32"))) / 255)
    h1 = cv2.calcHist([gray], [0], None, [64], [0, 256]); cv2.normalize(h1, h1)
    h0 = cv2.calcHist([pgray], [0], None, [64], [0, 256]); cv2.normalize(h0, h0)
    result["hist_change"] = max(0.0, min(1.0, 1 - float(cv2.compareHist(h1, h0, cv2.HISTCMP_CORREL))))
    flow = cv2.calcOpticalFlowFarneback(pgray, gray, None, .5, 2, 15, 3, 5, 1.1, 0)
    magnitude, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    result["flow"] = float(np.mean(magnitude) / 10)
    result["hflow"] = float(np.mean(flow[..., 0]) / 10)
    result["vflow"] = float(np.mean(flow[..., 1]) / 10)
    return result

def transition_kind(current, previous, nxt):
    if previous is None:
        return None
    difference, hist, flow = current["difference"], current["hist_change"], current["flow"]
    jump = current["brightness"] - previous["brightness"]
    if difference >= .22 and hist >= .18:
        return "hard_cut", min(99, int(62 + difference * 90 + hist * 45))
    if current["brightness"] >= .8 and jump >= .28:
        return "flash", min(96, int(65 + jump * 80))
    if previous["blur"] > 0 and current["blur"] < previous["blur"] * .28 and difference >= .10:
        return "blur_transition", min(90, int(55 + difference * 100))
    if flow >= .55 and max(abs(current["hflow"]), abs(current["vflow"])) >= .25:
        axis = "horizontal" if abs(current["hflow"]) >= abs(current["vflow"]) else "vertical"
        return f"whip_pan_{axis}", min(94, int(50 + flow * 55))
    if flow >= .28 and .06 <= hist < .22:
        return "zoom_transition", min(86, int(48 + flow * 60))
    if nxt is not None:
        a, b, c = previous["brightness"], current["brightness"], nxt["brightness"]
        if ((a > b > c) or (a < b < c)) and abs(a - c) >= .25:
            return "fade_or_dip", 58
    return None

def visual_analysis(source: Path, duration: float, interval: float):
    import cv2
    cap = cv2.VideoCapture(str(source))
    if not cap.isOpened():
        raise RuntimeError(f"OpenCV could not open {source}")
    samples, previous, t = [], None, 0.0
    while t < duration:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if ok:
            samples.append({"time": t, "frame": frame, **features(frame, previous)})
            previous = frame
        t += interval
    cap.release()

    transitions = []
    for index, row in enumerate(samples):
        result = transition_kind(
            row,
            samples[index - 1] if index else None,
            samples[index + 1] if index + 1 < len(samples) else None,
        )
        if result:
            kind, confidence = result
            if transitions and row["time"] - transitions[-1].time < .34:
                if confidence <= transitions[-1].confidence:
                    continue
                transitions.pop()
            transitions.append(Transition(
                round(row["time"], 3), kind, confidence,
                {"difference": round(row["difference"], 4),
                 "hist_change": round(row["hist_change"], 4),
                 "flow": round(row["flow"], 4)}
            ))

    boundaries = [0.0]
    for item in transitions:
        if item.kind in {"hard_cut", "flash", "fade_or_dip"} and item.time - boundaries[-1] >= .4:
            boundaries.append(item.time)
    if duration - boundaries[-1] >= .25:
        boundaries.append(duration)
    else:
        boundaries[-1] = duration

    key_dir = KEYFRAMES / safe(source)
    key_dir.mkdir(parents=True, exist_ok=True)
    scenes = []
    for index in range(len(boundaries) - 1):
        start, end = boundaries[index], boundaries[index + 1]
        rows = [x for x in samples if start <= x["time"] < end]
        if not rows:
            continue
        middle = rows[len(rows) // 2]
        key = key_dir / f"{index:03d}_{middle['time']:.2f}s.jpg"
        cv2.imwrite(str(key), middle["frame"])
        scenes.append(Scene(
            round(start, 3), round(end, 3), round(end - start, 3),
            round(float(np.mean([x["flow"] for x in rows])), 4),
            round(float(np.mean([x["brightness"] for x in rows])), 4),
            round(float(np.mean([x["text_density"] for x in rows])), 4),
            bool(np.mean([x["insert_score"] for x in rows]) >= .48),
            str(key.relative_to(BASE)).replace("\\", "/")
        ))

    visual_events = []
    for label, field_name, threshold in [
        ("caption_or_text_overlay", "text_density", .14),
        ("probable_image_or_meme_insert", "insert_score", .48),
    ]:
        active = None
        for row in samples:
            enabled = row[field_name] >= threshold
            if enabled and active is None:
                active = row["time"]
            if not enabled and active is not None:
                if row["time"] - active >= .35:
                    visual_events.append({
                        "start": round(active, 3),
                        "end": round(row["time"], 3),
                        "event_type": label,
                        "confidence": 66,
                    })
                active = None

    summary = {
        "scene_count": len(scenes),
        "transition_count": len(transitions),
        "average_scene_length": round(float(np.mean([s.duration for s in scenes])), 3) if scenes else duration,
        "cuts_per_10_seconds": round(sum(x.kind == "hard_cut" for x in transitions) / max(duration, .1) * 10, 2),
        "average_motion": round(float(np.mean([x["flow"] for x in samples])), 4) if samples else 0,
    }
    return scenes, transitions, visual_events, summary

def extract_audio(source: Path, target: Path) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found on PATH")
    result = subprocess.run(
        [ffmpeg, "-y", "-i", str(source), "-vn", "-ac", "1", "-ar", "22050",
         "-c:a", "pcm_s16le", str(target)],
        capture_output=True,
    )
    return result.returncode == 0 and target.exists()

def load_wav(path: Path):
    with wave.open(str(path), "rb") as stream:
        rate = stream.getframerate()
        channels = stream.getnchannels()
        width = stream.getsampwidth()
        raw = stream.readframes(stream.getnframes())
    if width != 2:
        raise RuntimeError("Expected 16-bit PCM")
    audio = np.frombuffer(raw, dtype=np.int16).astype("float32") / 32768
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    return audio, rate

def spectral(chunk, rate):
    if len(chunk) < 64:
        return {"rms": 0, "zcr": 0, "centroid": 0, "low": 0, "high": 0, "rise": 0}
    windowed = chunk * np.hanning(len(chunk))
    spectrum = np.abs(np.fft.rfft(windowed))
    frequencies = np.fft.rfftfreq(len(windowed), 1 / rate)
    total = float(spectrum.sum()) + 1e-8
    envelope = np.abs(chunk)
    split = max(1, len(envelope) // 3)
    return {
        "rms": float(np.sqrt(np.mean(chunk ** 2))),
        "zcr": float(np.mean(np.abs(np.diff(np.signbit(chunk)).astype("float32")))),
        "centroid": float(np.sum(frequencies * spectrum) / total) / (rate / 2),
        "low": float(spectrum[frequencies < 250].sum() / total),
        "high": float(spectrum[frequencies > 4000].sum() / total),
        "rise": float(envelope[-split:].mean() - envelope[:split].mean()),
    }

def sound_family(duration, features):
    if duration <= .18 and features["centroid"] >= .35 and features["zcr"] >= .12:
        return "click_or_ui_tick", 70
    if duration <= .32 and features["centroid"] >= .27 and features["high"] >= .08:
        return "pop_or_snap", 68
    if features["low"] >= .58 and duration <= 1.2:
        return "bass_hit_or_vine_boom", 76
    if features["rise"] > .035 and duration >= .45:
        return "riser_or_build_up", 67
    if features["centroid"] >= .40 and duration >= .25:
        return "whoosh_or_swipe", 64
    if features["low"] >= .38 and features["high"] >= .06:
        return "impact_or_explosion", 64
    if features["zcr"] >= .20 and duration >= .4:
        return "scream_noise_or_glitch", 58
    return "unknown_effect", 42

def audio_analysis(source: Path):
    with tempfile.TemporaryDirectory() as directory:
        wav = Path(directory) / "audio.wav"
        if not extract_audio(source, wav):
            return [], {"probable_voiceover": False, "probable_music_bed": False, "silence_ratio": 1}
        audio, rate = load_wav(wav)
    hop, window = int(rate * .1), int(rate * .3)
    rows = []
    for start in range(0, max(0, len(audio) - window), hop):
        row = spectral(audio[start:start + window], rate)
        row["time"] = start / rate
        rows.append(row)
    if not rows:
        return [], {}
    rms = np.array([x["rms"] for x in rows])
    silence = max(.003, float(np.percentile(rms, 15)))
    threshold = max(.012, float(np.percentile(rms, 82)), float(rms.mean() + rms.std() * 1.15))
    speech = [x["rms"] > silence and .025 <= x["zcr"] <= .19 and .08 <= x["centroid"] <= .48 for x in rows]
    music = [x["rms"] > silence and x["zcr"] < .16 and x["centroid"] < .42 for x in rows]
    events, active = [], None
    for index, row in enumerate(rows):
        enabled = row["rms"] >= threshold
        if enabled and active is None:
            active = index
        if not enabled and active is not None:
            segment = rows[active:index]
            if segment:
                start, end = segment[0]["time"], segment[-1]["time"] + .3
                aggregate = {key: float(np.mean([x[key] for x in segment]))
                             for key in ("rms", "zcr", "centroid", "low", "high", "rise")}
                family, confidence = sound_family(end - start, aggregate)
                peak = max(x["rms"] for x in segment)
                events.append(SoundEvent(
                    round(start, 3), round(end, 3), family, confidence,
                    round(20 * math.log10(max(peak, 1e-8)), 2)
                ))
            active = None
    return events, {
        "probable_voiceover": float(np.mean(speech)) >= .30,
        "probable_music_bed": float(np.mean(music)) >= .55,
        "probable_game_audio": float(np.mean(speech)) < .30 and float(np.mean(music)) < .55,
        "speech_ratio": round(float(np.mean(speech)), 4),
        "music_ratio": round(float(np.mean(music)), 4),
        "silence_ratio": round(float(np.mean(rms <= silence)), 4),
    }

def decompose_video(source_file: str | Path, sample_interval: float = .2) -> Decomposition:
    source = resolve(source_file).resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    metadata = probe_video(source)
    duration = float(metadata["duration"])
    scenes, transitions, visual_events, summary = visual_analysis(source, duration, max(.1, sample_interval))
    sounds, layers = audio_analysis(source)
    result = Decomposition(
        str(source.relative_to(BASE)).replace("\\", "/") if source.is_relative_to(BASE) else str(source),
        round(duration, 3), int(metadata["width"]), int(metadata["height"]), round(float(metadata["fps"]), 3),
        scenes, transitions, sounds, visual_events, layers, summary,
        ["SFX labels are heuristic families, not exact identities.",
         "OCR and exact Roblox object recognition are not enabled in v1."]
    )
    result.save()
    return result
