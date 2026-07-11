from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .analysis_review import load_review_bundle
from .full_video_analyzer import BASE
from .reference_library import ANALYZED_DIR, DB_PATH, FAILED_DIR, PENDING_DIR

OUTPUT_DIR = BASE / "outputs" / "map_analysis"


@dataclass
class PlatformObservation:
    frame_time: float
    x: float
    y: float
    width: float
    height: float
    confidence: int
    kind: str
    color_rgb: tuple[int, int, int]


@dataclass
class FrameEvidence:
    frame_time: float
    brightness: float
    edge_density: float
    horizontal_lines: int
    vertical_lines: int
    floor_score: float
    sky_score: float
    platform_count: int
    motion_x: float
    motion_y: float
    preview_path: str


@dataclass
class MapAnalysis:
    source_name: str
    source_path: str
    duration: float
    sampled_frames: int
    scene_family: str
    environment_type: str
    indoor_probability: int
    outdoor_probability: int
    platform_probability: int
    corridor_probability: int
    estimated_platform_count: int
    dominant_palette: list[tuple[int, int, int]]
    platform_observations: list[PlatformObservation]
    frame_evidence: list[FrameEvidence]
    camera_travel: str
    map_requirements: dict[str, Any]
    reconstruction_rules: list[str]
    confidence: int
    warnings: list[str] = field(default_factory=list)
    contact_sheet_path: str = ""

    def save(self) -> Path:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUTPUT_DIR / f"{_safe(self.source_name)}.map_analysis.json"
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        return path


def _safe(value: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in Path(str(value)).stem).strip("_") or "reference"


def resolve_reference_video(source_name: str) -> Path:
    for path in (ANALYZED_DIR / source_name, PENDING_DIR / source_name, FAILED_DIR / source_name):
        if path.exists():
            return path.resolve()
    if DB_PATH.exists():
        con = sqlite3.connect(DB_PATH)
        try:
            row = con.execute(
                "SELECT final_path, original_path FROM reference_runs WHERE source_name=? ORDER BY id DESC LIMIT 1",
                (source_name,),
            ).fetchone()
        finally:
            con.close()
        if row:
            for value in row:
                if value and Path(value).exists():
                    return Path(value).resolve()
    for folder in (ANALYZED_DIR, PENDING_DIR, FAILED_DIR):
        matches = list(folder.glob(f"{Path(source_name).stem}*")) if folder.exists() else []
        if matches:
            return matches[0].resolve()
    raise FileNotFoundError(f"Reference video could not be located for: {source_name}")


def _times(duration: float, count: int) -> list[float]:
    if duration <= 0:
        return [0.0]
    margin = min(0.25, duration * 0.04)
    return [margin + (duration - 2 * margin) * i / max(1, count - 1) for i in range(count)]


def _resize(frame: np.ndarray, width: int = 640) -> np.ndarray:
    height = max(1, int(frame.shape[0] * width / frame.shape[1]))
    return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)


def _palette(frame: np.ndarray, count: int = 3) -> list[tuple[int, int, int]]:
    small = cv2.resize(frame, (96, 54), interpolation=cv2.INTER_AREA)
    pixels = small.reshape(-1, 3).astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, labels, centers = cv2.kmeans(pixels, count, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
    frequencies = np.bincount(labels.flatten(), minlength=count)
    return [tuple(int(v) for v in centers[i][::-1]) for i in np.argsort(frequencies)[::-1]]


def _lines(edges: np.ndarray) -> tuple[int, int, list[tuple[int, int, int, int]]]:
    found = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=45, minLineLength=max(35, edges.shape[1] // 12), maxLineGap=18)
    horizontal = vertical = 0
    kept: list[tuple[int, int, int, int]] = []
    if found is None:
        return horizontal, vertical, kept
    for raw in found[:, 0]:
        x1, y1, x2, y2 = [int(v) for v in raw]
        angle = abs(math.degrees(math.atan2(y2 - y1, x2 - x1)))
        angle = min(angle, 180 - angle)
        if angle <= 14:
            horizontal += 1
            kept.append((x1, y1, x2, y2))
        elif angle >= 76:
            vertical += 1
            kept.append((x1, y1, x2, y2))
    return horizontal, vertical, kept


def _platforms(frame: np.ndarray, edges: np.ndarray, time_value: float) -> list[PlatformObservation]:
    height, width = frame.shape[:2]
    merged = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 3)), iterations=2)
    contours, _ = cv2.findContours(merged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rows: list[PlatformObservation] = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = (w * h) / float(width * height)
        aspect = w / max(h, 1)
        if area < 0.006 or area > 0.48 or aspect < 1.5 or h > height * 0.30 or y < height * 0.16:
            continue
        roi = frame[y:y+h, x:x+w]
        if roi.size == 0:
            continue
        bgr = np.mean(roi.reshape(-1, 3), axis=0)
        confidence = int(max(35, min(94, 44 + min(30, aspect * 4) + min(15, area * 180) + (y / height) * 8)))
        kind = "floor_or_path" if aspect >= 5 else "foreground_platform" if y > height * 0.68 else "platform"
        rows.append(PlatformObservation(round(time_value, 3), round(x / width, 4), round(y / height, 4), round(w / width, 4), round(h / height, 4), confidence, kind, tuple(int(v) for v in bgr[::-1])))
    rows.sort(key=lambda item: (item.confidence, item.width), reverse=True)
    return rows[:10]


def _floor(frame: np.ndarray, horizontal: int) -> float:
    lower = frame[int(frame.shape[0] * 0.55):]
    hsv = cv2.cvtColor(lower, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1].astype(np.float32) / 255.0
    val = hsv[:, :, 2].astype(np.float32) / 255.0
    consistency = 1.0 - min(1.0, float(np.std(val)) * 2.2)
    return float(max(0.0, min(1.0, 0.38 * consistency + 0.32 * float(np.mean(sat < 0.45)) + 0.30 * min(1.0, horizontal / 18.0))))


def _sky(frame: np.ndarray) -> float:
    top = frame[:max(1, int(frame.shape[0] * 0.28))]
    hsv = cv2.cvtColor(top, cv2.COLOR_BGR2HSV)
    hue, sat, val = hsv[:, :, 0], hsv[:, :, 1] / 255.0, hsv[:, :, 2] / 255.0
    blue = ((hue >= 85) & (hue <= 125) & (sat > 0.18)).mean()
    return float(max(0.0, min(1.0, blue * 0.70 + (val > 0.68).mean() * 0.30)))


def _motion(previous: np.ndarray | None, current: np.ndarray) -> tuple[float, float]:
    if previous is None:
        return 0.0, 0.0
    flow = cv2.calcOpticalFlowFarneback(cv2.resize(previous, (320, 180)), cv2.resize(current, (320, 180)), None, 0.5, 3, 15, 3, 5, 1.2, 0)
    return float(np.median(flow[:, :, 0])), float(np.median(flow[:, :, 1]))


def _annotate(frame: np.ndarray, observations: list[PlatformObservation], lines: list[tuple[int, int, int, int]], metrics: dict[str, Any]) -> np.ndarray:
    output = frame.copy()
    height, width = frame.shape[:2]
    for x1, y1, x2, y2 in lines:
        cv2.line(output, (x1, y1), (x2, y2), (70, 220, 255), 2)
    for index, item in enumerate(observations):
        x, y = int(item.x * width), int(item.y * height)
        w, h = int(item.width * width), int(item.height * height)
        cv2.rectangle(output, (x, y), (x + w, y + h), (80, 255, 110), 2)
        cv2.putText(output, f"P{index+1} {item.confidence}%", (x, max(18, y - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (80, 255, 110), 1, cv2.LINE_AA)
    cv2.rectangle(output, (0, 0), (width, 32), (15, 18, 24), -1)
    cv2.putText(output, f"floor {metrics['floor']:.2f} | sky {metrics['sky']:.2f} | H {metrics['horizontal']} | V {metrics['vertical']}", (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (245, 245, 245), 1, cv2.LINE_AA)
    return output


def _contact_sheet(paths: list[Path], output: Path) -> None:
    images = [cv2.imread(str(path)) for path in paths]
    images = [image for image in images if image is not None]
    if not images:
        return
    thumbs = []
    for image in images:
        width = 320
        thumbs.append(cv2.resize(image, (width, int(image.shape[0] * width / image.shape[1]))))
    columns = 3
    cell_height = max(image.shape[0] for image in thumbs)
    sheet = np.full((math.ceil(len(thumbs) / columns) * cell_height, columns * 320, 3), 22, dtype=np.uint8)
    for index, image in enumerate(thumbs):
        y, x = (index // columns) * cell_height, (index % columns) * 320
        sheet[y:y+image.shape[0], x:x+image.shape[1]] = image
    output.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output), sheet)


def analyze_map(source_name: str, sample_count: int = 18) -> MapAnalysis:
    source = resolve_reference_video(source_name)
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open reference video: {source}")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 30.0)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = frame_count / fps if frame_count else 0.0
    times = _times(duration, max(8, min(36, int(sample_count))))
    analysis_dir = OUTPUT_DIR / _safe(source_name)
    previews = analysis_dir / "frames"
    previews.mkdir(parents=True, exist_ok=True)

    evidence: list[FrameEvidence] = []
    observations: list[PlatformObservation] = []
    colors: list[tuple[int, int, int]] = []
    preview_paths: list[Path] = []
    previous: np.ndarray | None = None

    for index, time_value in enumerate(times):
        capture.set(cv2.CAP_PROP_POS_MSEC, time_value * 1000)
        ok, frame = capture.read()
        if not ok or frame is None:
            continue
        frame = _resize(frame)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 55, 145)
        horizontal, vertical, lines = _lines(edges)
        platforms = _platforms(frame, edges, time_value)
        floor_score, sky_score = _floor(frame, horizontal), _sky(frame)
        motion_x, motion_y = _motion(previous, gray)
        previous = gray
        colors.extend(_palette(frame))
        observations.extend(platforms)
        preview = previews / f"frame_{index:02d}_{time_value:.2f}.jpg"
        cv2.imwrite(str(preview), _annotate(frame, platforms, lines, {"floor": floor_score, "sky": sky_score, "horizontal": horizontal, "vertical": vertical}))
        preview_paths.append(preview)
        evidence.append(FrameEvidence(round(time_value, 3), round(float(np.mean(gray) / 255.0), 4), round(float(np.mean(edges > 0)), 4), horizontal, vertical, round(floor_score, 4), round(sky_score, 4), len(platforms), round(motion_x, 4), round(motion_y, 4), str(preview.relative_to(BASE)).replace("\\", "/")))
    capture.release()
    if not evidence:
        raise RuntimeError("No frames could be sampled from the reference video.")

    context = json.dumps(load_review_bundle(source_name), ensure_ascii=False).lower()
    avg_floor = float(np.mean([item.floor_score for item in evidence]))
    avg_sky = float(np.mean([item.sky_score for item in evidence]))
    h_total, v_total = sum(item.horizontal_lines for item in evidence), sum(item.vertical_lines for item in evidence)
    avg_platforms = float(np.mean([item.platform_count for item in evidence]))
    indoor = min(1.0, 0.55 * min(1.0, v_total / max(1, len(evidence) * 12)) + 0.45 * (1.0 - avg_sky))
    outdoor = min(1.0, 0.70 * avg_sky + 0.30 * (1.0 - indoor))
    platform_score = min(1.0, 0.55 * min(1.0, avg_platforms / 4.0) + 0.45 * min(1.0, h_total / max(1, len(evidence) * 14)))
    corridor = min(1.0, 0.65 * min(1.0, v_total / max(1, len(evidence) * 14)) + 0.35 * avg_floor)

    if "hospital" in context:
        family, environment = "hospital", "indoor_rooms"
    elif "horror" in context or "corridor" in context:
        family, environment = "horror_corridor", "indoor_corridor"
    elif "obby" in context or platform_score >= 0.64:
        family, environment = "obby", "platform_course"
    elif "city" in context or "street" in context:
        family, environment = "city", "outdoor_street"
    elif indoor >= 0.62:
        family, environment = "indoor_generic", "indoor_room"
    else:
        family, environment = "character_showcase", "open_showcase"

    motion_x = float(np.mean([item.motion_x for item in evidence]))
    motion_y = float(np.mean([item.motion_y for item in evidence]))
    camera_travel = "lateral" if abs(motion_x) > abs(motion_y) * 1.35 and abs(motion_x) > 0.12 else "forward_or_up" if motion_y < -0.12 else "backward_or_down" if motion_y > 0.12 else "mostly_static_or_follow"

    strong = sorted([item for item in observations if item.confidence >= 55], key=lambda item: item.confidence, reverse=True)[:24]
    counts: dict[tuple[int, int, int], int] = {}
    for color in colors:
        quantized = tuple(int(round(channel / 32) * 32) for channel in color)
        counts[quantized] = counts.get(quantized, 0) + 1
    dominant = [color for color, _ in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:6]]
    estimated = max(1, min(18, int(round(max(avg_platforms, len(strong) / max(1, len(evidence)))))))
    requirements = {
        "needs_base_floor": avg_floor >= 0.38 or family != "obby",
        "needs_platforms": family in {"obby", "character_showcase"} or platform_score >= 0.48,
        "needs_walls": indoor >= 0.55,
        "needs_ceiling": family in {"hospital", "horror_corridor", "indoor_generic"},
        "needs_corridor": corridor >= 0.58 or family == "horror_corridor",
        "needs_background_geometry": True,
        "estimated_platform_count": estimated,
        "minimum_action_zone_size": [30, 1, 26],
        "growth_clearance_studs": 36 if "grow" in context or "scale" in context else 14,
        "recommended_path_width": 12 if family == "obby" else 18,
        "recommended_camera_lane_width": 22,
        "camera_travel": camera_travel,
        "palette": dominant,
    }
    rules = [
        "Construct a connected path from spawn through every action zone.",
        "Keep jumps within a 10-stud horizontal gap unless a jump boost is generated.",
        "Reserve a camera lane beside or behind the player path.",
        "Use detected platform proportions as relative sizing, not literal pixel geometry.",
        "Add background geometry so the vertical crop never shows an empty void.",
        "Place the main transformation or reveal in the largest and clearest zone.",
        "Avoid overlapping collision volumes and ensure spawn sits above solid ground.",
    ]
    if requirements["needs_walls"]:
        rules.append("Create architectural wall shells around detected indoor zones.")
    if requirements["needs_ceiling"]:
        rules.append("Add a ceiling above indoor rooms with sufficient avatar clearance.")
    if requirements["needs_platforms"]:
        rules.append("Generate foreground, action, and landing platforms with visual hierarchy.")

    contact = analysis_dir / "contact_sheet.jpg"
    _contact_sheet(preview_paths, contact)
    confidence = int(max(45, min(96, 55 + min(18, len(evidence)) + min(12, len(strong) // 2) + (8 if family in context else 0))))
    result = MapAnalysis(source_name, str(source), round(duration, 3), len(evidence), family, environment, int(round(indoor * 100)), int(round(outdoor * 100)), int(round(platform_score * 100)), int(round(corridor * 100)), estimated, dominant, strong, evidence, camera_travel, requirements, rules, confidence, ["Exact Roblox stud dimensions cannot be recovered from one gameplay video; proportional reconstruction is used.", "Occluded geometry is replaced with structurally safe fallbacks."], str(contact.relative_to(BASE)).replace("\\", "/"))
    result.save()
    return result


def load_map_analysis(source_name: str) -> MapAnalysis | None:
    path = OUTPUT_DIR / f"{_safe(source_name)}.map_analysis.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    data["dominant_palette"] = [tuple(item) for item in data.get("dominant_palette", [])]
    data["platform_observations"] = [PlatformObservation(**{**item, "color_rgb": tuple(item["color_rgb"])}) for item in data.get("platform_observations", [])]
    data["frame_evidence"] = [FrameEvidence(**item) for item in data.get("frame_evidence", [])]
    return MapAnalysis(**data)
