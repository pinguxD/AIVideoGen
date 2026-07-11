from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .full_video_analyzer import BASE
from .map_blueprint import load_map_blueprint
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
        safe = "".join(
            char if char.isalnum() or char in "-_" else "_"
            for char in Path(self.source_name).stem
        )
        output = OUTPUT_DIR / f"{safe}.world_plan.json"
        output.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return output


def _validate(blueprint, platforms, walls, connections):
    errors = []
    repairs = []

    if blueprint.enclosure == "open":
        if any(wall.purpose == "ceiling" for wall in walls):
            errors.append("Open map contains a ceiling.")
        if any(
            wall.purpose in {"left_wall", "right_wall", "back_wall"}
            for wall in walls
        ):
            errors.append("Open map contains forbidden room shells.")

    maximum_backdrops = int(
        blueprint.rules.get("maximum_shared_backdrop_walls", 1)
    )
    backdrops = sum(wall.purpose == "backdrop_wall" for wall in walls)
    if backdrops > maximum_backdrops:
        errors.append(
            f"Generated {backdrops} backdrop walls; maximum is {maximum_backdrops}."
        )

    if not platforms:
        errors.append("No route platforms were generated.")

    for connection in connections:
        if connection.gap > 10:
            connection.gap = 9.0
            connection.repaired = True
            repairs.append(
                f"Reduced {connection.from_id} → {connection.to_id} gap."
            )

    return {
        "valid": not errors,
        "errors": errors,
        "repairs": repairs,
        "blueprint_status": blueprint.status,
        "platform_count": len(platforms),
        "wall_count": len(walls),
        "connection_count": len(connections),
    }


def build_world_plan(source_name: str) -> WorldPlan:
    blueprint = load_map_blueprint(source_name)
    if blueprint is None:
        raise FileNotFoundError(
            "No Map Blueprint exists. Build it from the full video first."
        )
    if blueprint.status != "APPROVED":
        raise RuntimeError(
            "Map Blueprint must be APPROVED before Roblox generation."
        )

    brain = (
        load_roblox_brain_plan(source_name)
        or build_roblox_brain_plan(source_name)
    )

    order = {
        structure_id: index
        for index, structure_id in enumerate(blueprint.depth_order)
    }
    route = sorted(
        [
            item
            for item in blueprint.structures
            if item.structure_type in {
                "platform",
                "walkway",
                "interaction_pad",
            }
        ],
        key=lambda item: order.get(item.structure_id, 999),
    )
    if not route:
        raise RuntimeError(
            "Approved Map Blueprint contains no route structures."
        )

    platforms = []
    zones = []
    player_path = []
    props = []

    for index, structure in enumerate(route):
        purpose = (
            structure.notes[0]
            if structure.notes
            else structure.structure_type
        )
        platform = Platform(
            platform_id=structure.structure_id,
            center=structure.world_position,
            size=structure.world_size,
            purpose=purpose,
            material="SmoothPlastic",
            color=structure.color_rgb,
            action=structure.mechanic,
            railing=False,
        )
        platforms.append(platform)
        player_path.append(
            (
                structure.world_position[0],
                structure.world_position[1] + 2.5,
                structure.world_position[2],
            )
        )
        clearance = 38.0 if structure.mechanic in {"grow", "shrink"} else 16.0
        zones.append(
            Zone(
                zone_id=f"zone_{structure.structure_id}",
                kind="route_zone",
                center=structure.world_position,
                size=(
                    max(structure.world_size[0], 10.0),
                    clearance,
                    max(structure.world_size[2], 8.0),
                ),
                purpose=purpose,
                clearance=clearance,
                style=blueprint.map_type,
            )
        )

        if structure.structure_type == "interaction_pad":
            props.append(
                {
                    "type": "interaction_pad",
                    "position": list(structure.world_position),
                    "size": list(structure.world_size),
                    "color": list(structure.color_rgb),
                    "mechanic": structure.mechanic or "grow",
                }
            )

    platform_lookup = {
        platform.platform_id: platform
        for platform in platforms
    }
    connections = []
    for item in blueprint.connections:
        left = platform_lookup.get(item.from_id)
        right = platform_lookup.get(item.to_id)
        if not left or not right:
            continue
        left_front = left.center[2] + left.size[2] / 2
        right_back = right.center[2] - right.size[2] / 2
        connections.append(
            Connection(
                from_id=item.from_id,
                to_id=item.to_id,
                kind=(
                    "walk_bridge"
                    if item.connection_type == "walkway"
                    else "jump_gap"
                ),
                width=min(left.size[0], right.size[0], 10.0),
                gap=round(max(0.0, right_back - left_front), 2),
                height_delta=round(
                    right.center[1] - left.center[1],
                    2,
                ),
            )
        )

    walls = []
    for structure in blueprint.structures:
        if structure.structure_type not in {
            "backdrop_wall",
            "shared_wall",
        }:
            continue
        walls.append(
            Wall(
                wall_id=structure.structure_id,
                center=structure.world_position,
                size=structure.world_size,
                color=structure.color_rgb,
                purpose="backdrop_wall",
            )
        )

    # A single global room shell may be created for an enclosed map.
    if (
        blueprint.enclosure == "enclosed"
        and blueprint.rules.get("generate_room_shells")
    ):
        min_x = min(item.center[0] - item.size[0] / 2 for item in platforms)
        max_x = max(item.center[0] + item.size[0] / 2 for item in platforms)
        min_z = min(item.center[2] - item.size[2] / 2 for item in platforms)
        max_z = max(item.center[2] + item.size[2] / 2 for item in platforms)
        width = max_x - min_x + 10
        depth = max_z - min_z + 10
        center_x = (min_x + max_x) / 2
        center_z = (min_z + max_z) / 2
        color = (
            blueprint.palette[0]
            if blueprint.palette
            else (90, 120, 180)
        )
        walls.extend(
            [
                Wall("global_left_wall", (center_x - width / 2, 10, center_z), (1, 20, depth), color, "left_wall"),
                Wall("global_right_wall", (center_x + width / 2, 10, center_z), (1, 20, depth), color, "right_wall"),
                Wall("global_back_wall", (center_x, 10, center_z + depth / 2), (width, 20, 1), color, "back_wall"),
            ]
        )
        if blueprint.rules.get("generate_ceiling"):
            walls.append(
                Wall(
                    "global_ceiling",
                    (center_x, 20, center_z),
                    (width, 1, depth),
                    color,
                    "ceiling",
                )
            )

    duration = float(getattr(brain, "duration", blueprint.duration))
    interval = max(0.8, duration / max(1, len(platforms)))
    gameplay = []
    for index, platform in enumerate(platforms):
        action = (
            platform.action
            or ("idle" if index == 0 else "walk")
        )
        gameplay.append(
            {
                "action": action,
                "start": round(index * interval, 2),
                "properties": {
                    "target_platform": platform.platform_id,
                    "target_position": list(player_path[index]),
                    "target_scale": 2.0 if action == "grow" else None,
                },
            }
        )

    camera_pattern = getattr(brain, "camera_pattern", {}) or {}
    camera_value = getattr(getattr(brain, "camera", None), "value", "third_person_follow")
    camera = [
        {
            "type": camera_value,
            "start": 0,
            "end": duration,
            "path": player_path,
            "lane_width": 20,
        },
        {
            "type": camera_pattern.get("dominant_pattern", "none"),
            "interval": camera_pattern.get("average_interval"),
            "occurrences": camera_pattern.get("occurrences", 0),
        },
    ]

    validation = _validate(
        blueprint,
        platforms,
        walls,
        connections,
    )

    plan = WorldPlan(
        source_name=source_name,
        scene_type=blueprint.map_type,
        layout_style="approved_full_video_map_blueprint",
        zones=zones,
        platforms=platforms,
        connections=connections,
        walls=walls,
        player_path=player_path,
        props=props,
        hazards=[],
        npc_specs=[],
        gameplay_specs=gameplay,
        camera_specs=camera,
        lighting=getattr(brain, "lighting", "bright_cartoon"),
        palette=blueprint.palette,
        map_analysis_confidence=blueprint.topology_confidence,
        confidence=int(
            round(
                blueprint.topology_confidence * 0.65
                + float(getattr(brain, "overall_confidence", 70)) * 0.35
            )
        ),
        validation=validation,
        warnings=list(blueprint.warnings),
    )
    plan.save()

    if not validation["valid"]:
        raise RuntimeError(
            "World Plan violates approved blueprint: "
            + "; ".join(validation["errors"])
        )

    return plan
