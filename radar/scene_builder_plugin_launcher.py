from __future__ import annotations

import os
import sys
import shutil
import subprocess
from pathlib import Path

from .full_video_analyzer import BASE

PLUGIN_SOURCE = Path(__file__).with_name("AIVideoGenPart3B.lua")
GENERATED_PLUGIN_DIR = BASE / "outputs" / "roblox_plugin"
GENERATED_PLUGIN_FILE = GENERATED_PLUGIN_DIR / "AIVideoGenPart3B.lua"


def generate_plugin_file() -> Path:
    if not PLUGIN_SOURCE.exists():
        raise FileNotFoundError(
            f"Bundled plugin source is missing: {PLUGIN_SOURCE}"
        )

    GENERATED_PLUGIN_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PLUGIN_SOURCE, GENERATED_PLUGIN_FILE)
    return GENERATED_PLUGIN_FILE


def find_roblox_studio() -> Path:
    configured = str(os.getenv("ROBLOX_STUDIO_PATH") or "").strip()
    if configured:
        path = Path(configured).expanduser()
        if path.exists():
            return path.resolve()
        raise FileNotFoundError(
            f"ROBLOX_STUDIO_PATH does not exist: {path}"
        )

    local_app_data = Path(
        os.getenv("LOCALAPPDATA")
        or Path.home() / "AppData" / "Local"
    )
    versions = local_app_data / "Roblox" / "Versions"
    candidates = list(
        versions.glob("*/RobloxStudioBeta.exe")
    ) + list(
        versions.glob("*/RobloxStudio.exe")
    )
    candidates = [path for path in candidates if path.exists()]

    if not candidates:
        raise FileNotFoundError(
            "Roblox Studio was not found. Set ROBLOX_STUDIO_PATH in .env."
        )

    return max(
        candidates,
        key=lambda path: path.stat().st_mtime,
    ).resolve()


def open_path(path: Path) -> None:
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
        return

    command = ["open", str(path)] if sys.platform == "darwin" else ["xdg-open", str(path)]
    subprocess.Popen(command)


def open_plugin_file() -> Path:
    path = generate_plugin_file()
    open_path(path)
    return path


def open_plugin_folder() -> Path:
    path = generate_plugin_file()
    open_path(path.parent)
    return path.parent


def launch_studio() -> tuple[Path, int]:
    studio = find_roblox_studio()
    process = subprocess.Popen(
        [str(studio)],
        cwd=str(BASE),
        creationflags=(
            subprocess.CREATE_NEW_PROCESS_GROUP
            if os.name == "nt"
            else 0
        ),
    )
    return studio, process.pid


def prepare_and_launch(
    open_plugin: bool = True,
    launch_roblox_studio: bool = True,
) -> dict[str, object]:
    plugin_path = generate_plugin_file()
    result: dict[str, object] = {
        "plugin_path": str(plugin_path),
        "plugin_opened": False,
        "studio_launched": False,
        "studio_path": "",
        "studio_pid": None,
        "warnings": [],
    }

    if open_plugin:
        try:
            open_path(plugin_path)
            result["plugin_opened"] = True
        except Exception as exc:
            result["warnings"].append(
                f"Could not open plugin file automatically: {exc}"
            )

    if launch_roblox_studio:
        try:
            studio, pid = launch_studio()
            result["studio_launched"] = True
            result["studio_path"] = str(studio)
            result["studio_pid"] = pid
        except Exception as exc:
            result["warnings"].append(
                f"Could not launch Roblox Studio automatically: {exc}"
            )

    return result
