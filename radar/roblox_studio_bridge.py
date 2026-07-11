from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .full_video_analyzer import BASE

JOBS_DIR = BASE / "outputs" / "roblox_jobs"
PENDING_DIR = JOBS_DIR / "pending"
LAUNCHED_DIR = JOBS_DIR / "launched"
FAILED_DIR = JOBS_DIR / "failed"
IMPORT_DIR = JOBS_DIR / "import_scripts"
LOG_DIR = JOBS_DIR / "logs"
STUDIO_PROJECTS_DIR = BASE / "outputs" / "roblox_studio_projects"

@dataclass
class StudioLaunchJob:
    job_id: str
    source_name: str
    status: str
    studio_executable: str
    template_place: str
    generated_lua: str
    scene_spec: str
    import_script: str
    output_log: str
    command: list[str]
    created_at: float
    launched_at: float | None = None
    process_id: int | None = None
    error: str = ""

    def save(self) -> Path:
        folder = {
            "PENDING": PENDING_DIR,
            "LAUNCHED": LAUNCHED_DIR,
            "FAILED": FAILED_DIR,
        }.get(self.status, PENDING_DIR)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{self.job_id}.json"
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        return path

def _safe_name(value: str | Path) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in Path(str(value)).stem).strip("_") or "reference"

def _latest_studio_executable() -> Path:
    configured = str(os.getenv("ROBLOX_STUDIO_PATH") or "").strip()
    if configured:
        path = Path(configured).expanduser()
        if path.exists():
            return path.resolve()
        raise FileNotFoundError(f"ROBLOX_STUDIO_PATH does not exist: {path}")

    local_app_data = Path(os.getenv("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    versions = local_app_data / "Roblox" / "Versions"
    candidates = list(versions.glob("*/RobloxStudioBeta.exe")) + list(versions.glob("*/RobloxStudio.exe"))
    candidates = [path for path in candidates if path.exists()]
    if not candidates:
        raise FileNotFoundError(
            "Roblox Studio was not found. Set ROBLOX_STUDIO_PATH in .env."
        )
    return max(candidates, key=lambda path: path.stat().st_mtime).resolve()

def _template_place() -> Path | None:
    configured = str(os.getenv("ROBLOX_TEMPLATE_PLACE") or "").strip()
    if not configured:
        return None
    path = Path(configured).expanduser()
    if not path.is_absolute():
        path = BASE / path
    if not path.exists():
        raise FileNotFoundError(f"ROBLOX_TEMPLATE_PLACE does not exist: {path}")
    if path.suffix.lower() not in {".rbxl", ".rbxlx"}:
        raise ValueError("ROBLOX_TEMPLATE_PLACE must be an .rbxl or .rbxlx file.")
    return path.resolve()

def _find_generated_project(source_name: str) -> tuple[Path, Path]:
    safe = _safe_name(source_name)
    folders = [STUDIO_PROJECTS_DIR / safe]
    if STUDIO_PROJECTS_DIR.exists():
        folders += sorted(
            [path for path in STUDIO_PROJECTS_DIR.glob(f"{safe}*") if path.is_dir()],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
    for folder in folders:
        lua_path = folder / "GeneratedScene.client.lua"
        spec_path = folder / "scene_spec.json"
        if lua_path.exists() and spec_path.exists():
            return lua_path.resolve(), spec_path.resolve()
    raise FileNotFoundError(
        f"No generated Roblox Studio project found for {source_name}. Run Recreation Lab again."
    )

def _long_bracket(text: str) -> str:
    for level in range(12):
        equals = "=" * level
        if f"]{equals}]" not in text:
            return f"[{equals}[{text}]{equals}]"
    raise ValueError("Could not safely embed generated Lua source.")

def _build_import_script(source_name: str, generated_lua_path: Path, scene_spec_path: Path, output_path: Path) -> Path:
    generated_lua = generated_lua_path.read_text(encoding="utf-8")
    scene_spec = scene_spec_path.read_text(encoding="utf-8")
    safe = _safe_name(source_name)

    importer = (
        "-- AIVideoGen Roblox Studio Importer - Stage 1\n"
        "local StarterPlayer = game:GetService(\"StarterPlayer\")\n"
        "local ReplicatedStorage = game:GetService(\"ReplicatedStorage\")\n"
        "local ServerScriptService = game:GetService(\"ServerScriptService\")\n"
        "local ChangeHistoryService = game:GetService(\"ChangeHistoryService\")\n"
        f"local packageName = \"AIVideoGen_{safe}\"\n"
        "local oldPackage = ReplicatedStorage:FindFirstChild(packageName)\n"
        "if oldPackage then oldPackage:Destroy() end\n"
        "local packageFolder = Instance.new(\"Folder\")\n"
        "packageFolder.Name = packageName\n"
        "packageFolder.Parent = ReplicatedStorage\n"
        "local manifest = Instance.new(\"StringValue\")\n"
        "manifest.Name = \"SceneSpecJSON\"\n"
        f"manifest.Value = {_long_bracket(scene_spec)}\n"
        "manifest.Parent = packageFolder\n"
        "local scriptsFolder = StarterPlayer:WaitForChild(\"StarterPlayerScripts\")\n"
        "local oldScript = scriptsFolder:FindFirstChild(\"GeneratedScene\")\n"
        "if oldScript then oldScript:Destroy() end\n"
        "local generatedScript = Instance.new(\"LocalScript\")\n"
        "generatedScript.Name = \"GeneratedScene\"\n"
        f"generatedScript.Source = {_long_bracket(generated_lua)}\n"
        f"generatedScript:SetAttribute(\"AIVideoGenSource\", \"{safe}\")\n"
        "generatedScript:SetAttribute(\"AIVideoGenImported\", true)\n"
        "generatedScript.Parent = scriptsFolder\n"
        "local marker = ServerScriptService:FindFirstChild(\"AIVideoGenImportInfo\")\n"
        "if marker then marker:Destroy() end\n"
        "marker = Instance.new(\"Folder\")\n"
        "marker.Name = \"AIVideoGenImportInfo\"\n"
        f"marker:SetAttribute(\"SourceName\", \"{safe}\")\n"
        "marker:SetAttribute(\"ImportedAtUnix\", os.time())\n"
        "marker.Parent = ServerScriptService\n"
        f"ChangeHistoryService:SetWaypoint(\"AIVideoGen imported {safe}\")\n"
        "print(\"[AIVideoGen] Import complete. Press Play to run GeneratedScene.\")\n"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(importer, encoding="utf-8")
    return output_path.resolve()

def _build_command(studio_path: Path, import_script: Path, output_log: Path, template_place: Path | None) -> list[str]:
    command = [str(studio_path), "--task", "RunScript"]
    if template_place is not None:
        command += ["--localPlaceFile", str(template_place)]
    command += ["--runScriptFile", str(import_script), "--outputFile", str(output_log)]
    return command

def create_launch_job(source_name: str) -> StudioLaunchJob:
    studio_path = _latest_studio_executable()
    template_place = _template_place()
    generated_lua, scene_spec = _find_generated_project(source_name)

    job_id = f"{int(time.time())}_{_safe_name(source_name)}_{uuid.uuid4().hex[:8]}"
    import_script = IMPORT_DIR / f"{job_id}.luau"
    output_log = LOG_DIR / f"{job_id}.log"

    _build_import_script(source_name, generated_lua, scene_spec, import_script)
    command = _build_command(studio_path, import_script, output_log, template_place)

    job = StudioLaunchJob(
        job_id=job_id,
        source_name=source_name,
        status="PENDING",
        studio_executable=str(studio_path),
        template_place=str(template_place or ""),
        generated_lua=str(generated_lua),
        scene_spec=str(scene_spec),
        import_script=str(import_script),
        output_log=str(output_log),
        command=command,
        created_at=time.time(),
    )
    job.save()
    return job

def launch_studio_job(job: StudioLaunchJob) -> StudioLaunchJob:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        process = subprocess.Popen(
            job.command,
            cwd=str(BASE),
            creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0),
        )
        job.status = "LAUNCHED"
        job.launched_at = time.time()
        job.process_id = process.pid
        job.save()
        pending = PENDING_DIR / f"{job.job_id}.json"
        if pending.exists():
            pending.unlink()
        return job
    except Exception as exc:
        job.status = "FAILED"
        job.error = str(exc)
        job.save()
        pending = PENDING_DIR / f"{job.job_id}.json"
        if pending.exists():
            pending.unlink()
        raise

def create_and_launch(source_name: str) -> StudioLaunchJob:
    return launch_studio_job(create_launch_job(source_name))

def list_jobs(limit: int = 100) -> list[dict[str, Any]]:
    rows = []
    for folder in (LAUNCHED_DIR, PENDING_DIR, FAILED_DIR):
        if not folder.exists():
            continue
        for path in folder.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                data["_job_file"] = str(path)
                rows.append(data)
            except Exception:
                continue
    rows.sort(key=lambda item: float(item.get("created_at") or 0), reverse=True)
    return rows[: max(1, int(limit))]
