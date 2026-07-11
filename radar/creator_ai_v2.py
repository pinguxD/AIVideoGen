from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .full_video_analyzer import BASE
from .roblox_brain import (
    build_roblox_brain_plan,
    load_roblox_brain_plan,
)
from .roblox_template_compiler import (
    TEMPLATE_PATH,
    compile_from_template,
    open_project,
)
from .scene_builder_engine import build_scene_package

RUNS_DIR = BASE / "outputs" / "creator_ai_v2_runs"


@dataclass
class StageResult:
    stage: str
    status: str
    message: str
    output: dict[str, Any] = field(default_factory=dict)


@dataclass
class CreatorRun:
    run_id: str
    source_name: str
    status: str
    stages: list[StageResult]
    started_at: float
    finished_at: float | None = None
    error: str = ""

    def save(self) -> Path:
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        path = RUNS_DIR / f"{self.run_id}.json"
        path.write_text(
            json.dumps(
                asdict(self),
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return path


def _stage(
    run: CreatorRun,
    name: str,
    message: str,
    output: dict[str, Any] | None = None,
) -> None:
    run.stages.append(
        StageResult(
            stage=name,
            status="DONE",
            message=message,
            output=output or {},
        )
    )
    run.save()


def generate_game(
    source_name: str,
    open_studio: bool = True,
) -> CreatorRun:
    run = CreatorRun(
        run_id=(
            f"{int(time.time())}_"
            f"{uuid.uuid4().hex[:8]}"
        ),
        source_name=source_name,
        status="RUNNING",
        stages=[],
        started_at=time.time(),
    )
    run.save()

    try:
        if not TEMPLATE_PATH.exists():
            raise FileNotFoundError(
                "No base Roblox template is installed. "
                "Upload a blank Baseplate .rbxlx once on the "
                "Creator AI v2 page."
            )

        brain = (
            load_roblox_brain_plan(source_name)
            or build_roblox_brain_plan(source_name)
        )
        _stage(
            run,
            "brain",
            "Video Blueprint loaded.",
            {
                "scene": brain.scene.value,
                "core_mechanic": brain.core_mechanic.value,
                "confidence": brain.overall_confidence,
            },
        )

        scene_build = build_scene_package(source_name)
        _stage(
            run,
            "builder_engine",
            "Modular Roblox scene package generated.",
            {
                "build_id": scene_build.build_id,
                "status": scene_build.status,
                "package_dir": scene_build.package_dir,
                "warnings": scene_build.warnings,
            },
        )

        package_dir = BASE / scene_build.package_dir
        compiled = compile_from_template(
            source_name=source_name,
            scene_package_dir=package_dir,
        )
        _stage(
            run,
            "place_compiler",
            "Template-based Roblox place compiled.",
            asdict(compiled),
        )

        if not compiled.valid:
            raise RuntimeError(
                "Compiled project did not pass local validation: "
                + "; ".join(compiled.errors)
            )

        if open_studio:
            open_project(compiled.place_path)
            _stage(
                run,
                "studio_sync",
                "GeneratedGame.rbxlx opened through Windows.",
                {
                    "place_path": compiled.place_path,
                },
            )

        run.status = "COMPLETED"
        run.finished_at = time.time()
        run.save()
        return run

    except Exception as exc:
        run.status = "FAILED"
        run.error = str(exc)
        run.finished_at = time.time()
        run.stages.append(
            StageResult(
                stage="error",
                status="FAILED",
                message=str(exc),
            )
        )
        run.save()
        raise


def list_runs(limit: int = 100) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not RUNS_DIR.exists():
        return rows

    for path in RUNS_DIR.glob("*.json"):
        try:
            rows.append(
                json.loads(path.read_text(encoding="utf-8"))
            )
        except (OSError, json.JSONDecodeError):
            continue

    rows.sort(
        key=lambda item: float(item.get("started_at") or 0),
        reverse=True,
    )
    return rows[: max(1, int(limit))]
