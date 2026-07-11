from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .full_video_analyzer import BASE
from .roblox_brain import (
    build_roblox_brain_plan,
    load_roblox_brain_plan,
)

JOBS_DIR = BASE / "outputs" / "roblox_plugin_jobs"
PENDING_DIR = JOBS_DIR / "pending"
ACTIVE_DIR = JOBS_DIR / "active"
COMPLETED_DIR = JOBS_DIR / "completed"
FAILED_DIR = JOBS_DIR / "failed"
STUDIO_PROJECTS_DIR = BASE / "outputs" / "roblox_studio_projects"


@dataclass
class PluginJob:
    job_id: str
    source_name: str
    status: str
    scene_spec: dict[str, Any]
    roblox_brain: dict[str, Any]
    generated_lua: str
    created_at: float
    claimed_at: float | None = None
    finished_at: float | None = None
    message: str = ""

    def save(self) -> Path:
        folder = {
            "PENDING": PENDING_DIR,
            "ACTIVE": ACTIVE_DIR,
            "COMPLETED": COMPLETED_DIR,
            "FAILED": FAILED_DIR,
        }.get(self.status, PENDING_DIR)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{self.job_id}.json"
        path.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path


def _safe_name(value: str | Path) -> str:
    return "".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in Path(str(value)).stem
    ).strip("_") or "reference"


def _find_generated_project(
    source_name: str,
) -> tuple[Path, Path]:
    safe = _safe_name(source_name)
    folders = [STUDIO_PROJECTS_DIR / safe]

    if STUDIO_PROJECTS_DIR.exists():
        folders.extend(
            sorted(
                [
                    path
                    for path in STUDIO_PROJECTS_DIR.glob(f"{safe}*")
                    if path.is_dir()
                ],
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
        )

    for folder in folders:
        lua_path = folder / "GeneratedScene.client.lua"
        spec_path = folder / "scene_spec.json"
        if lua_path.exists() and spec_path.exists():
            return lua_path, spec_path

    raise FileNotFoundError(
        f"No generated Roblox Studio project found for {source_name}."
    )


def create_plugin_job(source_name: str) -> PluginJob:
    generated_lua_path, scene_spec_path = _find_generated_project(
        source_name
    )

    brain_plan = (
        load_roblox_brain_plan(source_name)
        or build_roblox_brain_plan(source_name)
    )

    job = PluginJob(
        job_id=(
            f"{int(time.time())}_{_safe_name(source_name)}_"
            f"{uuid.uuid4().hex[:8]}"
        ),
        source_name=source_name,
        status="PENDING",
        scene_spec=json.loads(
            scene_spec_path.read_text(encoding="utf-8")
        ),
        roblox_brain=asdict(brain_plan),
        generated_lua=generated_lua_path.read_text(
            encoding="utf-8"
        ),
        created_at=time.time(),
    )
    job.save()
    return job


def _read_job(path: Path) -> PluginJob:
    return PluginJob(**json.loads(path.read_text(encoding="utf-8")))


def next_pending_job() -> PluginJob | None:
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    candidates = sorted(
        PENDING_DIR.glob("*.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not candidates:
        return None

    path = candidates[0]
    job = _read_job(path)
    job.status = "ACTIVE"
    job.claimed_at = time.time()
    job.save()
    path.unlink(missing_ok=True)
    return job


def complete_job(job_id: str, message: str = "") -> PluginJob:
    path = ACTIVE_DIR / f"{job_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Active job not found: {job_id}")
    job = _read_job(path)
    job.status = "COMPLETED"
    job.finished_at = time.time()
    job.message = message
    job.save()
    path.unlink(missing_ok=True)
    return job


def fail_job(job_id: str, message: str) -> PluginJob:
    path = ACTIVE_DIR / f"{job_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Active job not found: {job_id}")
    job = _read_job(path)
    job.status = "FAILED"
    job.finished_at = time.time()
    job.message = message
    job.save()
    path.unlink(missing_ok=True)
    return job


def list_plugin_jobs(limit: int = 100) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for folder in (
        PENDING_DIR,
        ACTIVE_DIR,
        COMPLETED_DIR,
        FAILED_DIR,
    ):
        if not folder.exists():
            continue
        for path in folder.glob("*.json"):
            try:
                rows.append(
                    json.loads(path.read_text(encoding="utf-8"))
                )
            except (OSError, json.JSONDecodeError):
                continue

    rows.sort(
        key=lambda item: float(item.get("created_at") or 0),
        reverse=True,
    )
    return rows[: max(1, int(limit))]
