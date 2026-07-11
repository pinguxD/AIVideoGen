from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from .full_video_analyzer import BASE
from .map_analyzer import analyze_map
from .roblox_template_compiler_v2 import TEMPLATE_PATH, compile_world, open_place
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
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        return path


def generate_complete_recreation(source_name: str, open_studio: bool = True) -> Run:
    run = Run(f"{int(time.time())}_{uuid.uuid4().hex[:8]}", source_name, "RUNNING", [], time.time())
    run.save()
    try:
        if not TEMPLATE_PATH.exists():
            raise FileNotFoundError("Install a blank Baseplate .rbxlx template once.")

        analysis = analyze_map(source_name)
        run.stages.append(Stage("map_analyzer", "DONE", "Reference geometry, platforms, walls, openness, palette and camera travel analyzed.", {"scene_family": analysis.scene_family, "platforms": analysis.estimated_platform_count, "confidence": analysis.confidence, "contact_sheet": analysis.contact_sheet_path}))
        run.save()

        plan = build_world_plan(source_name)
        run.stages.append(Stage("world_planner", "DONE", "Evidence-driven platforms, zones, connections, walls, props and gameplay route planned.", {"scene": plan.scene_type, "zones": len(plan.zones), "platforms": len(plan.platforms), "connections": len(plan.connections), "walls": len(plan.walls), "repairs": plan.validation.get("repairs", []), "confidence": plan.confidence}))
        run.save()

        compiled = compile_world(source_name, plan)
        run.stages.append(Stage("project_compiler", "DONE", "Advanced reconstructed Roblox map compiled and validated.", asdict(compiled)))
        run.save()
        if not compiled.valid:
            raise RuntimeError("; ".join(compiled.errors))

        if open_studio:
            open_place(compiled.place_path)
            run.stages.append(Stage("studio_sync", "DONE", "Generated place opened in Roblox Studio.", {"place_path": compiled.place_path}))
            run.save()

        run.status = "COMPLETED"
        run.finished_at = time.time()
        run.save()
        return run
    except Exception as exc:
        run.status = "FAILED"
        run.error = str(exc)
        run.finished_at = time.time()
        run.stages.append(Stage("error", "FAILED", str(exc)))
        run.save()
        raise


def list_runs(limit: int = 100) -> list[dict[str, Any]]:
    rows = []
    if RUNS.exists():
        for path in RUNS.glob("*.json"):
            try:
                rows.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                pass
    return sorted(rows, key=lambda item: item.get("started_at", 0), reverse=True)[:limit]
