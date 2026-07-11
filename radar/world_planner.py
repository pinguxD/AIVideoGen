from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .full_video_analyzer import BASE
from .map_analyzer import MapAnalysis, analyze_map, load_map_analysis
from .roblox_brain import build_roblox_brain_plan, load_roblox_brain_plan

OUTPUT_DIR = BASE / "outputs" / "world_plans"


@dataclass
class Zone:
    zone_id: str
    kind: str
    center: tuple[float, float, float]
    size: tuple[float, float, float]
    purpose: str
    clearance: float
    style: str
    props: list[str] = field(default_factory=list)


@dataclass
class Platform:
    platform_id: str
    center: tuple[float, float, float]
    size: tuple[float, float, float]
    purpose: str
    material: str
    color: tuple[int, int, int]
    action: str = ""
    railing: bool = False


@dataclass
class Connection:
    from_id: str
    to_id: str
    kind: str
    width: float
    gap: float
    height_delta: float
    repaired: bool = False


@dataclass
class Wall:
    wall_id: str
    center: tuple[float, float, float]
    size: tuple[float, float, float]
    color: tuple[int, int, int]
    purpose: str


@dataclass
class WorldPlan:
    source_name: str
    scene_type: str
    layout_style: str
    zones: list[Zone]
    platforms: list[Platform]
    connections: list[Connection]
    walls: list[Wall]
    player_path: list[tuple[float, float, float]]
    props: list[dict[str, Any]]
    hazards: list[dict[str, Any]]
    npc_specs: list[dict[str, Any]]
    gameplay_specs: list[dict[str, Any]]
    camera_specs: list[dict[str, Any]]
    lighting: str
    palette: list[tuple[int, int, int]]
    map_analysis_confidence: int
    confidence: int
    validation: dict[str, Any]
    warnings: list[str]

    def save(self) -> Path:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in Path(self.source_name).stem)
        path = OUTPUT_DIR / f"{safe}.world_plan.json"
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        return path


def _palette(analysis: MapAnalysis) -> list[tuple[int, int, int]]:
    colors = list(analysis.dominant_palette)
    for color in [(72, 174, 255), (95, 230, 150), (255, 196, 82), (235, 238, 245), (88, 96, 120), (245, 105, 120)]:
        if len(colors) >= 6:
            break
        colors.append(color)
    return colors[:6]


def _actions(brain: Any) -> list[str]:
    found = [item.value for item in [*brain.state_actions, *brain.event_actions]]
    ordered: list[str] = []
    for preferred in ("idle", "walk", "grow", "shrink", "jump", "turn", "reveal_object", "chase"):
        if preferred in found:
            ordered.append(preferred)
    for action in found:
        if action not in ordered:
            ordered.append(action)
    return ordered or ["walk"]


def _size(observation: Any | None, scene: str) -> tuple[float, float, float]:
    if observation is None:
        return (24.0, 1.0, 20.0)
    width = max(10.0, min(38.0, observation.width * 70.0))
    depth = max(8.0, min(30.0, observation.height * 85.0))
    if scene in {"hospital", "indoor_generic", "horror_corridor"}:
        width, depth = max(width, 18.0), max(depth, 16.0)
    return (round(width, 2), 1.0, round(depth, 2))


def _course(analysis: MapAnalysis, actions: list[str], scene: str, palette: list[tuple[int, int, int]]) -> tuple[list[Platform], list[Connection], list[tuple[float, float, float]]]:
    observations = analysis.platform_observations
    desired = max(len(actions) + 2, min(12, analysis.estimated_platform_count + 2))
    platforms: list[Platform] = []
    connections: list[Connection] = []
    path: list[tuple[float, float, float]] = []
    z_cursor = 0.0
    previous_height = 2.0

    for index in range(desired):
        observation = observations[index % len(observations)] if observations else None
        size = _size(observation, scene)
        color = observation.color_rgb if observation else palette[index % len(palette)]
        target_height = max(1.5, min(9.0, 2.0 + ((0.56 - observation.y) * 10.0 if observation else (index % 3) * 1.5)))
        action = actions[index] if index < len(actions) else ""
        purpose = "spawn" if index == 0 else "final_reveal" if index == desired - 1 else f"{action or 'movement'}_zone"
        if action in {"grow", "shrink"}:
            size = (max(size[0], 34.0), 1.0, max(size[2], 28.0))
            target_height = previous_height
        gap = 3.0 if index == 0 else 8.0 if action == "jump" else 5.0
        if action == "jump":
            target_height = min(previous_height + 3.5, 9.0)
        z_cursor += size[2] / 2.0 + gap
        center = (0.0, round(target_height, 2), round(z_cursor, 2))
        platform = Platform(f"platform_{index+1}", center, size, purpose, "SmoothPlastic", tuple(color), action, index not in {0, desired - 1} and scene != "obby")
        platforms.append(platform)
        path.append((center[0], center[1] + 2.5, center[2]))
        if index > 0:
            prior = platforms[index - 1]
            prior_front = prior.center[2] + prior.size[2] / 2.0
            current_back = center[2] - size[2] / 2.0
            actual_gap = max(0.0, current_back - prior_front)
            connections.append(Connection(prior.platform_id, platform.platform_id, "jump_gap" if action == "jump" else "walk_bridge", min(prior.size[0], size[0], 12.0), round(actual_gap, 2), round(center[1] - prior.center[1], 2)))
        z_cursor += size[2] / 2.0
        previous_height = target_height
    return platforms, connections, path


def _shell(zone: Zone, palette: list[tuple[int, int, int]], ceiling: bool) -> list[Wall]:
    cx, cy, cz = zone.center
    sx, sy, sz = zone.size
    color = palette[3]
    rows = [
        Wall(f"{zone.zone_id}_left", (cx - sx/2, cy + sy/2, cz), (1, sy, sz), color, "left_wall"),
        Wall(f"{zone.zone_id}_right", (cx + sx/2, cy + sy/2, cz), (1, sy, sz), color, "right_wall"),
        Wall(f"{zone.zone_id}_back", (cx, cy + sy/2, cz + sz/2), (sx, sy, 1), color, "back_wall"),
    ]
    if ceiling:
        rows.append(Wall(f"{zone.zone_id}_ceiling", (cx, cy + sy, cz), (sx, 1, sz), color, "ceiling"))
    return rows


def _validate(platforms: list[Platform], connections: list[Connection], clearance: float) -> dict[str, Any]:
    repairs: list[str] = []
    errors: list[str] = []
    for connection in connections:
        if connection.kind == "jump_gap" and connection.gap > 10:
            connection.gap = 9.0
            connection.repaired = True
            repairs.append(f"Reduced {connection.from_id} → {connection.to_id} jump gap.")
        if abs(connection.height_delta) > 5:
            connection.height_delta = max(-5.0, min(5.0, connection.height_delta))
            connection.repaired = True
            repairs.append(f"Limited height difference for {connection.to_id}.")
    for platform in platforms:
        if platform.action in {"grow", "shrink"} and platform.size[0] < clearance * 0.75:
            platform.size = (round(clearance * 0.75, 2), platform.size[1], max(platform.size[2], 28.0))
            repairs.append(f"Expanded {platform.platform_id} for transformation clearance.")
    for index, left in enumerate(platforms):
        for right in platforms[index + 1:]:
            dx, dz = abs(left.center[0] - right.center[0]), abs(left.center[2] - right.center[2])
            if dx < (left.size[0] + right.size[0]) / 2 and dz < (left.size[2] + right.size[2]) / 2:
                errors.append(f"Overlap detected between {left.platform_id} and {right.platform_id}.")
    return {"valid": not errors, "errors": errors, "repairs": repairs, "platform_count": len(platforms), "connection_count": len(connections)}


def build_world_plan(source_name: str) -> WorldPlan:
    brain = load_roblox_brain_plan(source_name) or build_roblox_brain_plan(source_name)
    analysis = load_map_analysis(source_name) or analyze_map(source_name)
    scene, palette, actions = analysis.scene_family, _palette(analysis), _actions(brain)
    platforms, connections, path = _course(analysis, actions, scene, palette)
    clearance = float(analysis.map_requirements.get("growth_clearance_studs", 14))
    zones = [Zone(f"zone_{index+1}", "room" if analysis.map_requirements.get("needs_walls") else "platform_zone", platform.center, (platform.size[0], clearance if platform.action in {"grow", "shrink"} else 14.0, platform.size[2]), platform.purpose, clearance if platform.action in {"grow", "shrink"} else 14.0, scene) for index, platform in enumerate(platforms)]
    walls: list[Wall] = []
    if analysis.map_requirements.get("needs_walls"):
        for zone in zones:
            walls.extend(_shell(zone, palette, bool(analysis.map_requirements.get("needs_ceiling"))))

    props: list[dict[str, Any]] = []
    hazards: list[dict[str, Any]] = []
    npcs: list[dict[str, Any]] = []
    if scene == "hospital":
        props = [
            {"type": "reception_desk", "position": [platforms[0].center[0], platforms[0].center[1] + 2, platforms[0].center[2] + 3]},
            {"type": "hospital_bed", "position": [platforms[-1].center[0] - 6, platforms[-1].center[1] + 1.5, platforms[-1].center[2]]},
            {"type": "hospital_bed", "position": [platforms[-1].center[0] + 6, platforms[-1].center[1] + 1.5, platforms[-1].center[2]]},
        ]
    elif scene == "horror_corridor":
        npcs = [{"type": "monster", "position": list(path[-1]), "behavior": "chase", "speed": 14}]
    elif scene == "obby":
        for index, platform in enumerate(platforms[1:-1], start=1):
            if index % 3 == 0:
                hazards.append({"type": "kill_block", "position": [platform.center[0], platform.center[1] + 0.75, platform.center[2]], "size": [min(platform.size[0] * 0.55, 10), 1, min(platform.size[2] * 0.55, 8)]})
    else:
        for index, platform in enumerate(platforms):
            props.append({"type": "accent_column", "position": [platform.center[0] - platform.size[0]/2 + 2, platform.center[1] + 4, platform.center[2]], "color": palette[index % len(palette)]})

    gameplay = []
    interval = max(0.8, brain.duration / max(1, len(actions)))
    for index, action in enumerate(actions):
        target_index = min(index + 1, len(platforms) - 1)
        properties: dict[str, Any] = {"target_platform": platforms[target_index].platform_id, "target_position": list(path[target_index])}
        if action == "grow":
            properties["target_scale"] = brain.character_state.get("scale", 2) if isinstance(brain.character_state, dict) else getattr(brain.character_state, "scale", 2)
        gameplay.append({"action": action, "start": round(index * interval, 2), "properties": properties})

    camera = [
        {"type": brain.camera.value, "start": 0, "end": brain.duration, "path": path, "lane_width": analysis.map_requirements.get("recommended_camera_lane_width", 22)},
        {"type": brain.camera_pattern.get("dominant_pattern", "none"), "interval": brain.camera_pattern.get("average_interval"), "occurrences": brain.camera_pattern.get("occurrences", 0)},
    ]
    validation = _validate(platforms, connections, clearance)
    warnings = list(analysis.warnings) + list(validation.get("errors") or [])
    plan = WorldPlan(source_name, scene, "evidence_driven_linear_short", zones, platforms, connections, walls, path, props, hazards, npcs, gameplay, camera, brain.lighting, palette, analysis.confidence, int(round(brain.overall_confidence * 0.55 + analysis.confidence * 0.45)), validation, warnings)
    plan.save()
    return plan
