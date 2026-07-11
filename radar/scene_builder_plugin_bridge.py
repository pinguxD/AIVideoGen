from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .full_video_analyzer import BASE
from .scene_builder_engine import list_scene_builds

BUILDS_DIR = BASE / "outputs" / "scene_builder"
JOBS_DIR = BASE / "outputs" / "scene_builder_plugin_jobs"
PENDING_DIR = JOBS_DIR / "pending"
ACTIVE_DIR = JOBS_DIR / "active"
COMPLETED_DIR = JOBS_DIR / "completed"
FAILED_DIR = JOBS_DIR / "failed"


@dataclass
class StudioPackageJob:
    job_id: str
    build_id: str
    source_name: str
    status: str
    package_dir: str
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


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_job(path: Path) -> StudioPackageJob:
    return StudioPackageJob(**_read_json(path))


def _build_manifest_path(build_id: str) -> Path:
    return BUILDS_DIR / build_id / "build_manifest.json"


def _load_build(build_id: str) -> dict[str, Any]:
    path = _build_manifest_path(build_id)
    if not path.exists():
        raise FileNotFoundError(
            f"Part 3A build manifest not found: {path}"
        )
    return _read_json(path)


def queue_scene_build(build_id: str) -> StudioPackageJob:
    build = _load_build(build_id)
    status = str(build.get("status") or "")

    if status == "FAILED":
        raise RuntimeError(
            "This Part 3A package failed and cannot be installed in Studio."
        )

    package_dir = BUILDS_DIR / build_id
    if not package_dir.exists():
        raise FileNotFoundError(
            f"Scene package directory not found: {package_dir}"
        )

    job = StudioPackageJob(
        job_id=f"{int(time.time())}_{uuid.uuid4().hex[:10]}",
        build_id=build_id,
        source_name=str(build.get("source_name") or ""),
        status="PENDING",
        package_dir=str(package_dir),
        created_at=time.time(),
    )
    job.save()
    return job


def next_pending_job() -> StudioPackageJob | None:
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    candidates = sorted(
        PENDING_DIR.glob("*.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not candidates:
        return None

    source_path = candidates[0]
    job = _read_job(source_path)
    job.status = "ACTIVE"
    job.claimed_at = time.time()
    job.save()
    source_path.unlink(missing_ok=True)
    return job


def _artifact_kind(relative_path: str) -> str:
    lowered = relative_path.lower()
    if lowered.startswith("modules/mechanics/"):
        return "mechanic_module"
    if lowered.startswith("modules/"):
        return "module"
    if lowered.startswith("scripts/") and ".client." in lowered:
        return "client_script"
    if lowered.startswith("scripts/") and ".server." in lowered:
        return "server_script"
    if lowered.endswith(".json"):
        return "json"
    return "file"


def package_payload(job: StudioPackageJob) -> dict[str, Any]:
    package_dir = Path(job.package_dir)
    manifest = _load_build(job.build_id)

    blueprint_path = package_dir / "blueprint" / "roblox_brain.json"
    if not blueprint_path.exists():
        raise FileNotFoundError(
            f"Blueprint missing from package: {blueprint_path}"
        )
    blueprint = _read_json(blueprint_path)

    files: list[dict[str, Any]] = []
    for path in sorted(package_dir.rglob("*")):
        if not path.is_file():
            continue

        relative = str(path.relative_to(package_dir)).replace("\\", "/")
        if relative in {
            "build_manifest.json",
            "studio_handoff/plugin_package.json",
        }:
            continue

        if path.suffix.lower() not in {".lua", ".luau", ".json"}:
            continue

        files.append(
            {
                "relative_path": relative,
                "kind": _artifact_kind(relative),
                "content": path.read_text(encoding="utf-8"),
            }
        )

    return {
        "job_id": job.job_id,
        "build_id": job.build_id,
        "source_name": job.source_name,
        "build_status": manifest.get("status"),
        "blueprint": blueprint,
        "files": files,
        "missing_builders": list(
            manifest.get("missing_builders") or []
        ),
        "warnings": list(manifest.get("warnings") or []),
    }


def complete_job(
    job_id: str,
    message: str = "Studio package installed.",
) -> StudioPackageJob:
    path = ACTIVE_DIR / f"{job_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Active Studio job not found: {job_id}")

    job = _read_job(path)
    job.status = "COMPLETED"
    job.finished_at = time.time()
    job.message = message
    job.save()
    path.unlink(missing_ok=True)
    return job


def fail_job(job_id: str, message: str) -> StudioPackageJob:
    path = ACTIVE_DIR / f"{job_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Active Studio job not found: {job_id}")

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
                rows.append(_read_json(path))
            except (OSError, json.JSONDecodeError):
                continue

    rows.sort(
        key=lambda item: float(item.get("created_at") or 0),
        reverse=True,
    )
    return rows[: max(1, int(limit))]


def available_builds(limit: int = 100) -> list[dict[str, Any]]:
    return [
        build
        for build in list_scene_builds(limit)
        if str(build.get("status") or "") != "FAILED"
    ]
