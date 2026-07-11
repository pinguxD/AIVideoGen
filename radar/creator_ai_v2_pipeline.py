from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from .full_video_analyzer import BASE
from .map_blueprint import load_map_blueprint
from .roblox_template_compiler_v2 import (
    TEMPLATE_PATH,
    compile_world,
    open_place,
)
from .world_planner import build_world_plan

RUNS = BASE / "outputs" / "creator_ai_v2_runs"


@dataclass
class Stage:
    name: str
    status: str
    message: str
    output: dict[str, Any] = field(default_factory=dict)


@dataclass
class Run:
    run_id: str
    source_name: str
    status: str
    stages: list[Stage]
    started_at: float
    finished_at: float | None = None
    error: str = ""

    def save(self):
        RUNS.mkdir(parents=True, exist_ok=True)
        path = RUNS / f"{self.run_id}.json"
        path.write_text(
            json.dumps(asdict(self), indent=2),
            encoding="utf-8",
        )
        return path


def generate_complete_recreation(
    source_name: str,
    open_studio: bool = True,
) -> Run:
    run = Run(
        f"{int(time.time())}_{uuid.uuid4().hex[:8]}",
        source_name,
        "RUNNING",
        [],
        time.time(),
    )
    run.save()

    try:
        if not TEMPLATE_PATH.exists():
            raise FileNotFoundError(
                "Install a blank Baseplate .rbxlx template once."
            )

        blueprint = load_map_blueprint(source_name)
        if blueprint is None:
            raise FileNotFoundError(
                "No Map Blueprint exists. Watch the full video and build it first."
            )
        if blueprint.status != "APPROVED":
            raise RuntimeError(
                "Map Blueprint is not approved. Review and approve it before generation."
            )

        run.stages.append(
            Stage(
                "map_blueprint_gate",
                "DONE",
                "Approved full-video Map Blueprint loaded.",
                {
                    "map_type": blueprint.map_type,
                    "enclosure": blueprint.enclosure,
                    "structures": len(blueprint.structures),
                    "frames_examined": blueprint.frames_examined,
                    "confidence": blueprint.topology_confidence,
                    "preview": blueprint.preview_path,
                },
            )
        )
        run.save()

        plan = build_world_plan(source_name)
        run.stages.append(
            Stage(
                "world_planner",
                "DONE",
                "Approved blueprint converted into a constrained Roblox World Plan.",
                {
                    "scene": plan.scene_type,
                    "platforms": len(plan.platforms),
                    "connections": len(plan.connections),
                    "walls": len(plan.walls),
                    "validation": plan.validation,
                },
            )
        )
        run.save()

        compiled = compile_world(source_name, plan)
        run.stages.append(
            Stage(
                "project_compiler",
                "DONE",
                "Roblox place compiled from the approved Map Blueprint.",
                asdict(compiled),
            )
        )
        run.save()

        if not compiled.valid:
            raise RuntimeError("; ".join(compiled.errors))

        if open_studio:
            open_place(compiled.place_path)
            run.stages.append(
                Stage(
                    "studio_sync",
                    "DONE",
                    "Generated place opened in Roblox Studio.",
                    {"place_path": compiled.place_path},
                )
            )
            run.save()

        run.status = "COMPLETED"
        run.finished_at = time.time()
        run.save()
        return run

    except Exception as exc:
        run.status = "FAILED"
        run.error = str(exc)
        run.finished_at = time.time()
        run.stages.append(
            Stage("error", "FAILED", str(exc))
        )
        run.save()
        raise


def list_runs(limit: int = 100) -> list[dict[str, Any]]:
    rows = []
    if RUNS.exists():
        for path in RUNS.glob("*.json"):
            try:
                rows.append(
                    json.loads(path.read_text(encoding="utf-8"))
                )
            except Exception:
                pass
    return sorted(
        rows,
        key=lambda item: item.get("started_at", 0),
        reverse=True,
    )[:limit]
