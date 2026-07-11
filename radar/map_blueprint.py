from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .full_video_analyzer import BASE
from .map_analyzer import resolve_reference_video

OUTPUT_DIR = BASE / "outputs" / "map_blueprints"


@dataclass
class TrackedStructure:
    structure_id: str
    structure_type: str
    confidence: int
    observations: int
    first_seen: float
    last_seen: float
    screen_bbox: tuple[float, float, float, float]
    relative_depth: str
    color_rgb: tuple[int, int, int]
    world_size: tuple[float, float, float]
    world_position: tuple[float, float, float]
    shared: bool = False
    mechanic: str = ""
    notes: list[str] = field(default_factory=list)


@dataclass
class MapConnection:
    from_id: str
    to_id: str
    connection_type: str
    order: int
    confidence: int


@dataclass
class MapBlueprint:
    source_name: str
    source_path: str
    duration: float
    frames_examined: int
    map_type: str
    enclosure: str
    sky_visibility: int
    topology_confidence: int
    structures: list[TrackedStructure]
    connections: list[MapConnection]
    depth_order: list[str]
    palette: list[tuple[int, int, int]]
    rules: dict[str, Any]
    unresolved: list[dict[str, Any]]
    evidence: dict[str, Any]
    preview_path: str
    contact_sheet_path: str
    status: str = "DRAFT"
    approved_at: float | None = None
    edited_by_user: bool = False
    warnings: list[str] = field(default_factory=list)

    def save(self) -> Path:
        folder = OUTPUT_DIR / _safe(self.source_name)
        folder.mkdir(parents=True, exist_ok=True)
        output = folder / "MapBlueprint.json"
        output.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return output


def _safe(value: str) -> str:
    return "".join(
        char if char.isalnum() or char in "-_" else "_"
        for char in Path(str(value)).stem
    ).strip("_") or "reference"


def _sample_times(duration: float) -> list[float]:
    count = max(60, min(140, int(round(max(duration, 10.0) * 6))))
    if duration <= 0:
        return [0.0]
    return [
        duration * index / max(1, count - 1)
        for index in range(count)
    ]


def _resize(frame: np.ndarray, width: int = 480) -> np.ndarray:
    height = max(1, int(frame.shape[0] * width / frame.shape[1]))
    return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)


def _overlay_mask(frames: list[np.ndarray]) -> np.ndarray:
    stack = np.stack(
        [cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) for frame in frames],
        axis=0,
    ).astype(np.float32)
    variance = np.var(stack, axis=0)
    mean = np.mean(stack, axis=0).astype(np.uint8)
    edges = cv2.Canny(mean, 70, 150) > 0
    stable = variance < np.percentile(variance, 18)

    mask = (stable & edges).astype(np.uint8) * 255
    height, width = mask.shape
    border = np.zeros_like(mask)
    border[: int(height * 0.30), :] = 255
    border[:, : int(width * 0.28)] = 255
    border[:, int(width * 0.82) :] = 255
    border[int(height * 0.82) :, :] = 255
    mask = cv2.bitwise_and(mask, border)
    return cv2.dilate(
        mask,
        cv2.getStructuringElement(cv2.MORPH_RECT, (9, 7)),
        iterations=2,
    )


def _clean(frame: np.ndarray, overlay_mask: np.ndarray) -> np.ndarray:
    height, width = frame.shape[:2]
    avatar_mask = np.zeros((height, width), dtype=np.uint8)
    cv2.ellipse(
        avatar_mask,
        (width // 2, int(height * 0.62)),
        (int(width * 0.17), int(height * 0.28)),
        0,
        0,
        360,
        255,
        -1,
    )
    combined = cv2.bitwise_or(overlay_mask, avatar_mask)
    output = frame.copy()
    blurred = cv2.medianBlur(frame, 21)
    output[combined > 0] = blurred[combined > 0]
    return output


def _sky_score(frame: np.ndarray) -> float:
    top = frame[: int(frame.shape[0] * 0.42), :]
    hsv = cv2.cvtColor(top, cv2.COLOR_BGR2HSV)
    hue = hsv[:, :, 0]
    saturation = hsv[:, :, 1] / 255.0
    value = hsv[:, :, 2] / 255.0
    blue = ((hue >= 84) & (hue <= 128) & (saturation > 0.18)).mean()
    bright = (value > 0.68).mean()
    return float(min(1.0, blue * 0.76 + bright * 0.24))


def _surface_detections(
    frame: np.ndarray,
    timestamp: float,
) -> list[dict[str, Any]]:
    height, width = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 55, 145)
    edges = cv2.morphologyEx(
        edges,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (9, 3)),
        iterations=2,
    )
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rows: list[dict[str, Any]] = []

    for contour in contours:
        x, y, box_w, box_h = cv2.boundingRect(contour)
        area = box_w * box_h / float(width * height)
        aspect = box_w / max(box_h, 1)
        if not 0.004 <= area <= 0.55:
            continue

        roi = frame[y : y + box_h, x : x + box_w]
        if roi.size == 0:
            continue
        bgr = np.mean(roi.reshape(-1, 3), axis=0)
        rgb = tuple(int(value) for value in bgr[::-1])

        structure_type = ""
        confidence = 0
        if aspect >= 1.8 and y > height * 0.20 and box_h < height * 0.36:
            structure_type = "walkway" if aspect >= 4.8 else "platform"
            confidence = int(min(94, 50 + aspect * 5 + area * 110))
        elif box_h / max(box_w, 1) >= 1.35 and area >= 0.015:
            structure_type = "vertical_surface"
            confidence = int(min(92, 54 + box_h / max(box_w, 1) * 7 + area * 80))

        if structure_type:
            rows.append(
                {
                    "type": structure_type,
                    "time": timestamp,
                    "bbox": (x / width, y / height, box_w / width, box_h / height),
                    "color": rgb,
                    "confidence": confidence,
                }
            )

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    red = cv2.bitwise_or(
        cv2.inRange(hsv, np.array([0, 100, 90]), np.array([12, 255, 255])),
        cv2.inRange(hsv, np.array([168, 100, 90]), np.array([179, 255, 255])),
    )
    contours, _ = cv2.findContours(red, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for contour in contours:
        x, y, box_w, box_h = cv2.boundingRect(contour)
        area = box_w * box_h / float(width * height)
        aspect = box_w / max(box_h, 1)
        if 0.004 <= area <= 0.22 and 0.65 <= aspect <= 2.8 and y > height * 0.35:
            rows.append(
                {
                    "type": "interaction_pad",
                    "time": timestamp,
                    "bbox": (x / width, y / height, box_w / width, box_h / height),
                    "color": (235, 45, 40),
                    "confidence": int(min(96, 68 + area * 180)),
                }
            )
    return rows


def _bbox_distance(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> float:
    lx, ly, lw, lh = left
    rx, ry, rw, rh = right
    return (
        abs((lx + lw / 2) - (rx + rw / 2))
        + abs((ly + lh / 2) - (ry + rh / 2))
        + abs(lw - rw) * 0.55
        + abs(lh - rh) * 0.55
    )


def _color_distance(
    left: tuple[int, int, int],
    right: tuple[int, int, int],
) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right))) / 441.7


def _track(detections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tracks: list[dict[str, Any]] = []
    for detection in sorted(detections, key=lambda item: item["time"]):
        best = None
        best_score = 999.0
        for index, track in enumerate(tracks):
            if track["type"] != detection["type"]:
                continue
            if detection["time"] - track["last_seen"] > 4.0:
                continue
            score = (
                _bbox_distance(track["bbox"], detection["bbox"])
                + _color_distance(track["color"], detection["color"]) * 0.65
            )
            if score < best_score:
                best_score = score
                best = index

        threshold = 0.48 if detection["type"] == "vertical_surface" else 0.36
        if best is None or best_score > threshold:
            tracks.append(
                {
                    "type": detection["type"],
                    "bbox": detection["bbox"],
                    "color": detection["color"],
                    "first_seen": detection["time"],
                    "last_seen": detection["time"],
                    "observations": 1,
                    "confidences": [detection["confidence"]],
                }
            )
            continue

        track = tracks[best]
        count = track["observations"]
        track["bbox"] = tuple(
            (track["bbox"][index] * count + detection["bbox"][index]) / (count + 1)
            for index in range(4)
        )
        track["color"] = tuple(
            int((track["color"][index] * count + detection["color"][index]) / (count + 1))
            for index in range(3)
        )
        track["observations"] += 1
        track["last_seen"] = detection["time"]
        track["confidences"].append(detection["confidence"])
    return tracks


def _depth(bbox: tuple[float, float, float, float]) -> str:
    bottom = bbox[1] + bbox[3]
    if bottom >= 0.78:
        return "foreground"
    if bottom >= 0.55:
        return "middle"
    return "background"


def _world_size(
    structure_type: str,
    bbox: tuple[float, float, float, float],
    depth: str,
) -> tuple[float, float, float]:
    _, _, width, height = bbox
    scale = {"foreground": 1.2, "middle": 1.0, "background": 0.82}[depth]
    if structure_type == "backdrop_wall":
        return (round(max(34, width * 105) * scale, 2), round(max(24, height * 76), 2), 1.2)
    if structure_type == "walkway":
        return (round(max(7, width * 58) * scale, 2), 1.0, round(max(18, height * 130) * scale, 2))
    if structure_type == "interaction_pad":
        return (round(max(7, width * 50), 2), 0.8, round(max(7, height * 60), 2))
    return (round(max(12, width * 72) * scale, 2), 1.0, round(max(10, height * 82) * scale, 2))


def _build_structures(
    tracks: list[dict[str, Any]],
    sky_visibility: int,
) -> tuple[list[TrackedStructure], list[MapConnection], list[str]]:
    vertical = [track for track in tracks if track["type"] == "vertical_surface"]
    route_tracks = [
        track
        for track in tracks
        if track["type"] in {"platform", "walkway", "interaction_pad"}
    ]

    # Cross-frame dedupe.
    kept: list[dict[str, Any]] = []
    for track in sorted(
        route_tracks,
        key=lambda item: (item["observations"], np.mean(item["confidences"])),
        reverse=True,
    ):
        duplicate = any(
            track["type"] == existing["type"]
            and _bbox_distance(track["bbox"], existing["bbox"]) < 0.22
            and _color_distance(track["color"], existing["color"]) < 0.30
            for existing in kept
        )
        if not duplicate:
            kept.append(track)
    route_tracks = kept[:8]
    route_tracks.sort(key=lambda item: ({"foreground": 0, "middle": 1, "background": 2}[_depth(item["bbox"])], item["bbox"][1]))

    structures: list[TrackedStructure] = []
    depth_order: list[str] = []
    z_cursor = 0.0

    for index, track in enumerate(route_tracks, start=1):
        depth = _depth(track["bbox"])
        structure_type = track["type"]
        size = _world_size(structure_type, track["bbox"], depth)
        z_cursor += size[2] / 2 + (2.0 if structure_type == "walkway" else 5.0)
        purpose = (
            "spawn_platform"
            if index == 1
            else "trigger_pad"
            if structure_type == "interaction_pad"
            else "final_reveal_platform"
            if index == len(route_tracks)
            else "walkway"
            if structure_type == "walkway"
            else "action_platform"
        )
        structure_id = f"route_{index}_{structure_type}"
        structure = TrackedStructure(
            structure_id=structure_id,
            structure_type=structure_type,
            confidence=int(round(np.mean(track["confidences"]))),
            observations=track["observations"],
            first_seen=round(track["first_seen"], 3),
            last_seen=round(track["last_seen"], 3),
            screen_bbox=tuple(round(value, 4) for value in track["bbox"]),
            relative_depth=depth,
            color_rgb=tuple(track["color"]),
            world_size=size,
            world_position=(0.0, {"foreground": 2.0, "middle": 3.0, "background": 4.5}[depth], round(z_cursor, 2)),
            mechanic="grow" if structure_type == "interaction_pad" else "",
            notes=[purpose],
        )
        structures.append(structure)
        depth_order.append(structure_id)
        z_cursor += size[2] / 2

    if vertical:
        strongest = max(
            vertical,
            key=lambda item: (item["observations"], np.mean(item["confidences"])),
        )
        wall_type = "backdrop_wall" if sky_visibility >= 25 else "shared_wall"
        size = _world_size("backdrop_wall", strongest["bbox"], _depth(strongest["bbox"]))
        structures.append(
            TrackedStructure(
                structure_id="shared_backdrop_wall",
                structure_type=wall_type,
                confidence=int(round(np.mean(strongest["confidences"]))),
                observations=sum(item["observations"] for item in vertical),
                first_seen=min(item["first_seen"] for item in vertical),
                last_seen=max(item["last_seen"] for item in vertical),
                screen_bbox=tuple(round(value, 4) for value in strongest["bbox"]),
                relative_depth="shared",
                color_rgb=tuple(strongest["color"]),
                world_size=(max(size[0], 30.0), max(size[1], 24.0), 1.2),
                world_position=(-max(10.0, size[0] * 0.33), max(size[1] / 2, 12.0), max(z_cursor / 2, 20.0)),
                shared=True,
                notes=["One shared backdrop bordering the route."],
            )
        )

    connections = []
    for index in range(len(depth_order) - 1):
        left = depth_order[index]
        right = depth_order[index + 1]
        right_structure = next(item for item in structures if item.structure_id == right)
        connections.append(
            MapConnection(
                from_id=left,
                to_id=right,
                connection_type="walkway" if right_structure.structure_type == "walkway" else "short_gap",
                order=index + 1,
                confidence=min(
                    next(item for item in structures if item.structure_id == left).confidence,
                    right_structure.confidence,
                ),
            )
        )

    return structures, connections, depth_order


def _palette(frames: list[np.ndarray]) -> list[tuple[int, int, int]]:
    pixels = []
    for frame in frames[:: max(1, len(frames) // 12)]:
        pixels.append(cv2.resize(frame, (64, 36)).reshape(-1, 3))
    data = np.concatenate(pixels, axis=0).astype(np.float32)
    _, labels, centers = cv2.kmeans(
        data,
        6,
        None,
        (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 25, 1.0),
        3,
        cv2.KMEANS_PP_CENTERS,
    )
    counts = np.bincount(labels.flatten(), minlength=6)
    return [
        tuple(int(value) for value in centers[index][::-1])
        for index in np.argsort(counts)[::-1]
    ]


def _draw_preview(blueprint: MapBlueprint, output: Path) -> None:
    canvas = np.full((900, 900, 3), (18, 22, 31), dtype=np.uint8)
    route = [
        item
        for item in blueprint.structures
        if item.structure_type in {"platform", "walkway", "interaction_pad"}
    ]
    max_z = max([item.world_position[2] for item in route] or [50]) + 20
    scale = 720 / max_z

    for item in route:
        x, _, z = item.world_position
        sx, _, sz = item.world_size
        center_x = 450 + int(x * scale)
        center_y = 820 - int(z * scale)
        box_w = max(22, int(sx * scale))
        box_h = max(16, int(sz * scale))
        color = tuple(int(value) for value in item.color_rgb[::-1])
        cv2.rectangle(
            canvas,
            (center_x - box_w // 2, center_y - box_h // 2),
            (center_x + box_w // 2, center_y + box_h // 2),
            color,
            -1,
        )
        cv2.rectangle(
            canvas,
            (center_x - box_w // 2, center_y - box_h // 2),
            (center_x + box_w // 2, center_y + box_h // 2),
            (245, 245, 245),
            2,
        )
        cv2.putText(
            canvas,
            item.notes[0] if item.notes else item.structure_type,
            (max(10, center_x - box_w // 2), max(30, center_y - box_h // 2 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (245, 245, 245),
            1,
            cv2.LINE_AA,
        )

    for connection in blueprint.connections:
        left = next(item for item in route if item.structure_id == connection.from_id)
        right = next(item for item in route if item.structure_id == connection.to_id)
        left_point = (450 + int(left.world_position[0] * scale), 820 - int(left.world_position[2] * scale))
        right_point = (450 + int(right.world_position[0] * scale), 820 - int(right.world_position[2] * scale))
        cv2.arrowedLine(canvas, left_point, right_point, (110, 225, 255), 3, tipLength=0.08)

    for item in blueprint.structures:
        if item.structure_type not in {"backdrop_wall", "shared_wall"}:
            continue
        center_x = 450 + int(item.world_position[0] * scale)
        center_y = 820 - int(item.world_position[2] * scale)
        span = max(80, int(item.world_size[0] * scale))
        cv2.line(
            canvas,
            (center_x, max(80, center_y - span // 2)),
            (center_x, min(820, center_y + span // 2)),
            tuple(int(value) for value in item.color_rgb[::-1]),
            16,
        )
        cv2.putText(canvas, "shared backdrop", (max(10, center_x - 120), max(45, center_y - span // 2 - 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (245, 245, 245), 1)

    cv2.putText(
        canvas,
        f"{blueprint.map_type} | {blueprint.enclosure} | confidence {blueprint.topology_confidence}%",
        (28, 42),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.72,
        (245, 245, 245),
        2,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output), canvas)


def _contact_sheet(frames: list[np.ndarray], output: Path) -> None:
    selected = frames[:: max(1, len(frames) // 12)][:12]
    sheet = np.full((169 * 4, 300 * 3, 3), 24, dtype=np.uint8)
    for index, frame in enumerate(selected):
        thumb = cv2.resize(frame, (300, 169))
        row = index // 3
        column = index % 3
        sheet[row * 169 : (row + 1) * 169, column * 300 : (column + 1) * 300] = thumb
    output.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output), sheet)


def build_map_blueprint(source_name: str) -> MapBlueprint:
    source_path = resolve_reference_video(source_name)
    capture = cv2.VideoCapture(str(source_path))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open reference video: {source_path}")

    fps = float(capture.get(cv2.CAP_PROP_FPS) or 30.0)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = frame_count / fps if frame_count else 0.0

    frames: list[np.ndarray] = []
    timestamps: list[float] = []
    for timestamp in _sample_times(duration):
        capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
        ok, frame = capture.read()
        if ok and frame is not None:
            frames.append(_resize(frame))
            timestamps.append(timestamp)
    capture.release()

    if len(frames) < 8:
        raise RuntimeError("Too few frames could be read from the reference video.")

    overlay = _overlay_mask(frames)
    cleaned = [_clean(frame, overlay) for frame in frames]
    sky_visibility = int(round(np.mean([_sky_score(frame) for frame in cleaned]) * 100))

    detections = []
    for frame, timestamp in zip(cleaned, timestamps):
        detections.extend(_surface_detections(frame, timestamp))

    tracks = _track(detections)
    structures, connections, depth_order = _build_structures(tracks, sky_visibility)

    route_count = sum(item.structure_type in {"platform", "walkway", "interaction_pad"} for item in structures)
    map_type = (
        "open_sky_showcase"
        if sky_visibility >= 38 and route_count >= 2
        else "open_showcase_with_backdrop"
        if sky_visibility >= 25
        else "indoor_route"
    )
    enclosure = "open" if sky_visibility >= 25 else "enclosed"

    confidence = int(
        max(
            48,
            min(
                96,
                52 + min(18, len(frames) // 5) + min(14, route_count * 3),
            ),
        )
    )

    folder = OUTPUT_DIR / _safe(source_name)
    preview_path = folder / "map_preview.png"
    contact_path = folder / "full_video_contact_sheet.jpg"

    unresolved = []
    if route_count < 3:
        unresolved.append(
            {
                "issue": "route_under_detected",
                "message": "Fewer than three route structures were confidently tracked.",
                "fallback": "Generate spawn, trigger, walkway and reveal platform.",
            }
        )
    if not any(item.structure_type == "interaction_pad" for item in structures):
        unresolved.append(
            {
                "issue": "trigger_pad_not_detected",
                "message": "No red trigger pad was confidently tracked.",
                "fallback": "Add one red growth trigger pad.",
            }
        )

    blueprint = MapBlueprint(
        source_name=source_name,
        source_path=str(source_path),
        duration=round(duration, 3),
        frames_examined=len(frames),
        map_type=map_type,
        enclosure=enclosure,
        sky_visibility=sky_visibility,
        topology_confidence=confidence,
        structures=structures,
        connections=connections,
        depth_order=depth_order,
        palette=_palette(cleaned),
        rules={
            "generate_room_shells": enclosure == "enclosed",
            "generate_ceiling": enclosure == "enclosed",
            "maximum_shared_backdrop_walls": 1 if enclosure == "open" else 4,
            "preserve_open_sky": sky_visibility >= 30,
            "compile_only_approved_blueprint": True,
            "minimum_route_platforms": 3,
            "maximum_route_platforms": 8,
            "interaction_pad_mechanic": "grow",
            "never_create_room_per_platform": True,
        },
        unresolved=unresolved,
        evidence={
            "raw_detection_count": len(detections),
            "tracked_object_count": len(tracks),
            "route_structure_count": route_count,
            "overlay_mask_coverage": round(float(np.mean(overlay > 0)), 4),
            "sample_times": [round(value, 3) for value in timestamps],
        },
        preview_path=str(preview_path.relative_to(BASE)).replace("\\", "/"),
        contact_sheet_path=str(contact_path.relative_to(BASE)).replace("\\", "/"),
        warnings=[
            "This reconstructs topology and proportions rather than exact hidden 3D geometry.",
            "Hidden geometry is replaced with safe connected fallbacks.",
        ],
    )
    _draw_preview(blueprint, preview_path)
    _contact_sheet(cleaned, contact_path)
    blueprint.save()
    return blueprint


def load_map_blueprint(source_name: str) -> MapBlueprint | None:
    path = OUTPUT_DIR / _safe(source_name) / "MapBlueprint.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return MapBlueprint(
        source_name=data["source_name"],
        source_path=data["source_path"],
        duration=float(data["duration"]),
        frames_examined=int(data["frames_examined"]),
        map_type=data["map_type"],
        enclosure=data["enclosure"],
        sky_visibility=int(data["sky_visibility"]),
        topology_confidence=int(data["topology_confidence"]),
        structures=[
            TrackedStructure(
                **{
                    **item,
                    "screen_bbox": tuple(item["screen_bbox"]),
                    "color_rgb": tuple(item["color_rgb"]),
                    "world_size": tuple(item["world_size"]),
                    "world_position": tuple(item["world_position"]),
                }
            )
            for item in data.get("structures", [])
        ],
        connections=[MapConnection(**item) for item in data.get("connections", [])],
        depth_order=list(data.get("depth_order") or []),
        palette=[tuple(item) for item in data.get("palette", [])],
        rules=dict(data.get("rules") or {}),
        unresolved=list(data.get("unresolved") or []),
        evidence=dict(data.get("evidence") or {}),
        preview_path=data.get("preview_path", ""),
        contact_sheet_path=data.get("contact_sheet_path", ""),
        status=data.get("status", "DRAFT"),
        approved_at=data.get("approved_at"),
        edited_by_user=bool(data.get("edited_by_user", False)),
        warnings=list(data.get("warnings") or []),
    )


def approve_map_blueprint(source_name: str) -> MapBlueprint:
    blueprint = load_map_blueprint(source_name)
    if blueprint is None:
        raise FileNotFoundError("Map Blueprint does not exist.")
    blueprint.status = "APPROVED"
    blueprint.approved_at = time.time()
    blueprint.save()
    return blueprint


def update_map_blueprint(
    source_name: str,
    payload: dict[str, Any],
) -> MapBlueprint:
    blueprint = load_map_blueprint(source_name)
    if blueprint is None:
        raise FileNotFoundError("Map Blueprint does not exist.")

    blueprint.map_type = str(payload.get("map_type", blueprint.map_type))
    blueprint.enclosure = str(payload.get("enclosure", blueprint.enclosure))
    blueprint.sky_visibility = int(payload.get("sky_visibility", blueprint.sky_visibility))

    if isinstance(payload.get("structures"), list):
        blueprint.structures = [
            TrackedStructure(
                structure_id=str(item["structure_id"]),
                structure_type=str(item["structure_type"]),
                confidence=int(item.get("confidence", 80)),
                observations=int(item.get("observations", 1)),
                first_seen=float(item.get("first_seen", 0)),
                last_seen=float(item.get("last_seen", blueprint.duration)),
                screen_bbox=tuple(item.get("screen_bbox", [0, 0, 0.2, 0.2])),
                relative_depth=str(item.get("relative_depth", "middle")),
                color_rgb=tuple(item.get("color_rgb", [180, 180, 180])),
                world_size=tuple(item.get("world_size", [20, 1, 16])),
                world_position=tuple(item.get("world_position", [0, 2, 0])),
                shared=bool(item.get("shared", False)),
                mechanic=str(item.get("mechanic") or ""),
                notes=list(item.get("notes") or []),
            )
            for item in payload["structures"]
        ]

    blueprint.edited_by_user = True
    blueprint.status = "DRAFT"
    blueprint.approved_at = None
    preview = OUTPUT_DIR / _safe(source_name) / "map_preview.png"
    _draw_preview(blueprint, preview)
    blueprint.save()
    return blueprint
