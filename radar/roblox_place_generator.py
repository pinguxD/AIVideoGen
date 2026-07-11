from __future__ import annotations

import json
import os
import subprocess
import time
import mimetypes
import shutil
import uuid
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from .full_video_analyzer import BASE
from .scene_builder_engine import list_scene_builds

SCENE_BUILDS_DIR = BASE / "outputs" / "scene_builder"
PLACE_OUTPUT_DIR = BASE / "outputs" / "generated_places"
PROJECT_OUTPUT_DIR = BASE / "outputs" / "generated_projects"


@dataclass
class GeneratedPlace:
    build_id: str
    source_name: str
    place_path: str
    manifest_path: str
    status: str
    studio_launched: bool = False
    studio_pid: int | None = None
    message: str = ""


class Referents:
    def __init__(self) -> None:
        self._value = 0

    def next(self) -> str:
        self._value += 1
        return f"RBX{self._value:X}"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_build(build_id: str | None = None) -> dict[str, Any]:
    if build_id:
        path = SCENE_BUILDS_DIR / build_id / "build_manifest.json"
        if not path.exists():
            raise FileNotFoundError(f"Part 3A build not found: {path}")
        return _read_json(path)

    builds = list_scene_builds(1)
    if not builds:
        raise FileNotFoundError(
            "No Part 3A build exists. Build a scene package first."
        )
    return builds[0]


def _package_dir(build: dict[str, Any]) -> Path:
    build_id = str(build.get("build_id") or "").strip()
    path = SCENE_BUILDS_DIR / build_id
    if not path.exists():
        raise FileNotFoundError(f"Part 3A package folder missing: {path}")
    return path


def _property(tag: str, name: str, value: Any) -> str:
    if tag == "string" or tag == "ProtectedString":
        return f'<{tag} name="{escape(name)}">{escape(str(value))}</{tag}>'
    if tag == "bool":
        text = "true" if bool(value) else "false"
        return f'<bool name="{escape(name)}">{text}</bool>'
    return f'<{tag} name="{escape(name)}">{value}</{tag}>'


def _vector3(name: str, xyz: tuple[float, float, float]) -> str:
    x, y, z = xyz
    return (
        f'<Vector3 name="{escape(name)}">'
        f"<X>{x}</X><Y>{y}</Y><Z>{z}</Z>"
        "</Vector3>"
    )


def _cframe(name: str, xyz: tuple[float, float, float]) -> str:
    x, y, z = xyz
    return (
        f'<CoordinateFrame name="{escape(name)}">'
        f"<X>{x}</X><Y>{y}</Y><Z>{z}</Z>"
        "<R00>1</R00><R01>0</R01><R02>0</R02>"
        "<R10>0</R10><R11>1</R11><R12>0</R12>"
        "<R20>0</R20><R21>0</R21><R22>1</R22>"
        "</CoordinateFrame>"
    )


def _color_uint8(rgb: tuple[int, int, int]) -> int:
    r, g, b = [max(0, min(255, int(value))) for value in rgb]
    return (255 << 24) | (r << 16) | (g << 8) | b


def _item(
    class_name: str,
    referent: str,
    properties: list[str],
    children: list[str] | None = None,
) -> str:
    return (
        f'<Item class="{escape(class_name)}" referent="{referent}">'
        "<Properties>"
        + "".join(properties)
        + "</Properties>"
        + "".join(children or [])
        + "</Item>"
    )


def _part(
    refs: Referents,
    name: str,
    size: tuple[float, float, float],
    position: tuple[float, float, float],
    rgb: tuple[int, int, int],
    class_name: str = "Part",
) -> str:
    return _item(
        class_name,
        refs.next(),
        [
            _property("bool", "Anchored", True),
            _property("bool", "CanCollide", True),
            _property("string", "Name", name),
            _cframe("CFrame", position),
            _vector3("size", size),
            _property(
                "Color3uint8",
                "Color3uint8",
                _color_uint8(rgb),
            ),
            _property("token", "Material", 256),
            _property("float", "Transparency", 0),
        ],
    )


def _environment_items(
    refs: Referents,
    blueprint: dict[str, Any],
) -> list[str]:
    graph = blueprint.get("environment_graph") or {}
    scene_type = str(graph.get("scene_type") or "simple_platform")
    items: list[str] = []

    if scene_type == "simple_obby":
        for index in range(10):
            items.append(
                _part(
                    refs,
                    f"Platform{index + 1}",
                    (8, 1, 8),
                    (index * 10, (index % 3) * 2, 0),
                    (
                        80 + (index * 17) % 175,
                        120 + (index * 23) % 135,
                        180 + (index * 11) % 75,
                    ),
                )
            )
    elif scene_type == "hospital":
        items.extend(
            [
                _part(
                    refs,
                    "HospitalFloor",
                    (60, 1, 50),
                    (0, 0, 0),
                    (225, 230, 235),
                ),
                _part(
                    refs,
                    "HospitalBackWall",
                    (60, 18, 1),
                    (0, 9, 25),
                    (185, 210, 225),
                ),
                _part(
                    refs,
                    "ReceptionDesk",
                    (14, 4, 3),
                    (0, 2, 8),
                    (110, 160, 195),
                ),
            ]
        )
    elif scene_type == "horror_corridor":
        items.extend(
            [
                _part(
                    refs,
                    "CorridorFloor",
                    (18, 1, 80),
                    (0, 0, 0),
                    (42, 42, 42),
                ),
                _part(
                    refs,
                    "LeftWall",
                    (1, 18, 80),
                    (-9, 9, 0),
                    (30, 30, 30),
                ),
                _part(
                    refs,
                    "RightWall",
                    (1, 18, 80),
                    (9, 9, 0),
                    (30, 30, 30),
                ),
            ]
        )
    else:
        items.append(
            _part(
                refs,
                "GeneratedBaseplate",
                (80, 1, 80),
                (0, 0, 0),
                (210, 210, 210),
            )
        )

    items.append(
        _part(
            refs,
            "GeneratedSpawn",
            (8, 1, 8),
            (0, 1, 0),
            (90, 200, 120),
            class_name="SpawnLocation",
        )
    )
    return items


def _load_lua_files(package_dir: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for path in package_dir.rglob("*.lua"):
        relative = str(path.relative_to(package_dir)).replace("\\", "/")
        files[relative] = path.read_text(encoding="utf-8")
    for path in package_dir.rglob("*.luau"):
        relative = str(path.relative_to(package_dir)).replace("\\", "/")
        files[relative] = path.read_text(encoding="utf-8")
    return files


def _module_item(
    refs: Referents,
    name: str,
    source: str,
) -> str:
    return _item(
        "ModuleScript",
        refs.next(),
        [
            _property("string", "Name", name),
            _property("bool", "Disabled", False),
            _property("ProtectedString", "Source", source),
        ],
    )


def _local_script_item(
    refs: Referents,
    name: str,
    source: str,
) -> str:
    return _item(
        "LocalScript",
        refs.next(),
        [
            _property("string", "Name", name),
            _property("bool", "Disabled", False),
            _property("ProtectedString", "Source", source),
        ],
    )


def _folder_item(
    refs: Referents,
    name: str,
    children: list[str],
) -> str:
    return _item(
        "Folder",
        refs.next(),
        [_property("string", "Name", name)],
        children,
    )


def _modules_tree(
    refs: Referents,
    lua_files: dict[str, str],
) -> str:
    normal_modules: list[str] = []
    mechanic_modules: list[str] = []

    for relative, source in sorted(lua_files.items()):
        if not relative.startswith("modules/"):
            continue
        name = Path(relative).stem
        item = _module_item(refs, name, source)
        if relative.startswith("modules/mechanics/"):
            mechanic_modules.append(item)
        else:
            normal_modules.append(item)

    mechanics_folder = _folder_item(
        refs,
        "Mechanics",
        mechanic_modules,
    )
    return _folder_item(
        refs,
        "Modules",
        [*normal_modules, mechanics_folder],
    )


def _lighting_properties(blueprint: dict[str, Any]) -> list[str]:
    preset = str(blueprint.get("lighting") or "bright_cartoon")
    if preset == "dark_horror":
        brightness, clock, ambient = 1.0, 1.0, (25, 25, 35)
    elif preset == "clean_indoor":
        brightness, clock, ambient = 2.5, 13.0, (170, 180, 195)
    else:
        brightness, clock, ambient = 3.0, 14.0, (150, 160, 180)

    return [
        _property("string", "Name", "Lighting"),
        _property("float", "Brightness", brightness),
        _property("float", "ClockTime", clock),
        _property(
            "Color3uint8",
            "Ambient",
            _color_uint8(ambient),
        ),
    ]



@dataclass
class PlaceValidation:
    valid_xml: bool
    has_workspace: bool
    has_replicated_storage: bool
    has_starter_player: bool
    has_generated_scene: bool
    has_package_modules: bool
    size_bytes: int
    under_100_mb: bool
    errors: list[str]
    warnings: list[str]

    @property
    def valid(self) -> bool:
        return (
            self.valid_xml
            and self.has_workspace
            and self.has_replicated_storage
            and self.has_starter_player
            and self.has_generated_scene
            and self.has_package_modules
            and self.under_100_mb
            and not self.errors
        )


def validate_place_file(place_path: str | Path) -> PlaceValidation:
    path = Path(place_path)
    errors: list[str] = []
    warnings: list[str] = []

    if not path.exists():
        return PlaceValidation(
            valid_xml=False,
            has_workspace=False,
            has_replicated_storage=False,
            has_starter_player=False,
            has_generated_scene=False,
            has_package_modules=False,
            size_bytes=0,
            under_100_mb=True,
            errors=[f"Place file does not exist: {path}"],
            warnings=[],
        )

    size_bytes = path.stat().st_size
    under_100_mb = size_bytes <= 104_857_600
    if not under_100_mb:
        errors.append("Place exceeds Roblox's documented 100 MB place limit.")

    try:
        root = ET.parse(path).getroot()
        valid_xml = root.tag == "roblox"
    except ET.ParseError as exc:
        return PlaceValidation(
            valid_xml=False,
            has_workspace=False,
            has_replicated_storage=False,
            has_starter_player=False,
            has_generated_scene=False,
            has_package_modules=False,
            size_bytes=size_bytes,
            under_100_mb=under_100_mb,
            errors=[f"XML parse failed: {exc}", *errors],
            warnings=warnings,
        )

    def item_names(class_name: str) -> list[str]:
        values: list[str] = []
        for item in root.findall(f".//Item[@class='{class_name}']"):
            name = item.find("./Properties/string[@name='Name']")
            if name is not None and name.text:
                values.append(name.text)
        return values

    has_workspace = "Workspace" in item_names("Workspace")
    has_replicated_storage = (
        "ReplicatedStorage" in item_names("ReplicatedStorage")
    )
    has_starter_player = "StarterPlayer" in item_names("StarterPlayer")
    has_generated_scene = "GeneratedScene" in item_names("LocalScript")

    folder_names = item_names("Folder")
    has_package_modules = (
        "AIVideoGenPackage" in folder_names
        and "Modules" in folder_names
    )

    if not has_workspace:
        errors.append("Workspace service is missing.")
    if not has_replicated_storage:
        errors.append("ReplicatedStorage service is missing.")
    if not has_starter_player:
        errors.append("StarterPlayer service is missing.")
    if not has_generated_scene:
        errors.append("GeneratedScene LocalScript is missing.")
    if not has_package_modules:
        errors.append("AIVideoGenPackage/Modules hierarchy is missing.")

    module_count = len(item_names("ModuleScript"))
    if module_count == 0:
        warnings.append("No ModuleScripts were embedded.")

    if size_bytes < 1_000:
        warnings.append(
            "Place file is unusually small; Studio may reject an incomplete place."
        )

    return PlaceValidation(
        valid_xml=valid_xml,
        has_workspace=has_workspace,
        has_replicated_storage=has_replicated_storage,
        has_starter_player=has_starter_player,
        has_generated_scene=has_generated_scene,
        has_package_modules=has_package_modules,
        size_bytes=size_bytes,
        under_100_mb=under_100_mb,
        errors=errors,
        warnings=warnings,
    )


def _create_project_folder(
    source_name: str,
    build_id: str,
    place_path: Path,
    blueprint: dict[str, Any],
    lua_files: dict[str, str],
    manifest: dict[str, Any],
) -> Path:
    safe_source = "".join(
        c if c.isalnum() or c in "-_" else "_"
        for c in Path(source_name).stem
    ).strip("_") or "GeneratedGame"

    project_dir = PROJECT_OUTPUT_DIR / f"{safe_source}_{build_id}"
    if project_dir.exists():
        shutil.rmtree(project_dir)
    project_dir.mkdir(parents=True, exist_ok=True)

    project_place = project_dir / "GeneratedGame.rbxlx"
    shutil.copy2(place_path, project_place)

    (project_dir / "blueprint.json").write_text(
        json.dumps(blueprint, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (project_dir / "metadata.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    for relative, content in lua_files.items():
        destination = project_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")

    for folder_name in ("assets", "sounds", "thumbnails"):
        (project_dir / folder_name).mkdir(exist_ok=True)

    return project_dir


def _windows_open_file(path: Path) -> None:
    if os.name != "nt":
        raise RuntimeError("Windows file association opening is only available on Windows.")
    os.startfile(str(path))  # type: ignore[attr-defined]


def _launch_studio_positional(
    studio: Path,
    place: Path,
) -> tuple[int, list[str]]:
    command = [str(studio), str(place)]
    process = subprocess.Popen(
        command,
        cwd=str(place.parent),
        creationflags=(
            subprocess.CREATE_NEW_PROCESS_GROUP
            if os.name == "nt"
            else 0
        ),
    )
    return process.pid, command

def generate_place(build_id: str | None = None) -> GeneratedPlace:
    build = _latest_build(build_id)
    package_dir = _package_dir(build)
    build_id = str(build.get("build_id") or "")
    source_name = str(build.get("source_name") or build_id)

    blueprint_path = package_dir / "blueprint" / "roblox_brain.json"
    if not blueprint_path.exists():
        raise FileNotFoundError(
            f"Part 2A blueprint missing: {blueprint_path}"
        )
    blueprint = _read_json(blueprint_path)
    lua_files = _load_lua_files(package_dir)

    refs = Referents()

    generated_folder = _folder_item(
        refs,
        "AIVideoGenGenerated",
        _environment_items(refs, blueprint),
    )

    workspace = _item(
        "Workspace",
        refs.next(),
        [_property("string", "Name", "Workspace")],
        [generated_folder],
    )

    lighting = _item(
        "Lighting",
        refs.next(),
        _lighting_properties(blueprint),
    )

    package_folder = _folder_item(
        refs,
        "AIVideoGenPackage",
        [
            _item(
                "StringValue",
                refs.next(),
                [
                    _property("string", "Name", "BlueprintJSON"),
                    _property(
                        "string",
                        "Value",
                        json.dumps(
                            blueprint,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    ),
                ],
            ),
            _modules_tree(refs, lua_files),
        ],
    )

    replicated_storage = _item(
        "ReplicatedStorage",
        refs.next(),
        [_property("string", "Name", "ReplicatedStorage")],
        [package_folder],
    )

    client_source = lua_files.get(
        "scripts/GeneratedScene.client.lua",
        (
            "warn('[AIVideoGen] GeneratedScene.client.lua was "
            "not found in the Part 3A package.')"
        ),
    )
    starter_player_scripts = _item(
        "StarterPlayerScripts",
        refs.next(),
        [_property("string", "Name", "StarterPlayerScripts")],
        [
            _local_script_item(
                refs,
                "GeneratedScene",
                client_source,
            )
        ],
    )
    starter_character_scripts = _item(
        "StarterCharacterScripts",
        refs.next(),
        [_property("string", "Name", "StarterCharacterScripts")],
    )
    starter_player = _item(
        "StarterPlayer",
        refs.next(),
        [_property("string", "Name", "StarterPlayer")],
        [starter_character_scripts, starter_player_scripts],
    )

    starter_gui = _item(
        "StarterGui",
        refs.next(),
        [_property("string", "Name", "StarterGui")],
    )
    server_script_service = _item(
        "ServerScriptService",
        refs.next(),
        [_property("string", "Name", "ServerScriptService")],
    )

    document = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<roblox xmlns:xmime="http://www.w3.org/2005/05/xmlmime" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'version="4">'
        "<External>null</External><External>nil</External>"
        + workspace
        + lighting
        + replicated_storage
        + starter_player
        + starter_gui
        + server_script_service
        + "</roblox>"
    )

    # Validate that the generated file is well-formed XML before saving it.
    ET.fromstring(document)

    PLACE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_source = "".join(
        c if c.isalnum() or c in "-_" else "_"
        for c in Path(source_name).stem
    ).strip("_") or "GeneratedGame"

    place_path = PLACE_OUTPUT_DIR / f"{safe_source}_{build_id}.rbxlx"
    place_path.write_text(document, encoding="utf-8")

    validation = validate_place_file(place_path)
    manifest = {
        "build_id": build_id,
        "source_name": source_name,
        "place_path": str(place_path),
        "generated_at": time.time(),
        "lua_files_embedded": sorted(lua_files),
        "scene_type": (
            (blueprint.get("environment_graph") or {}).get("scene_type")
        ),
        "lighting": blueprint.get("lighting"),
        "validation": asdict(validation),
    }

    project_dir = _create_project_folder(
        source_name=source_name,
        build_id=build_id,
        place_path=place_path,
        blueprint=blueprint,
        lua_files=lua_files,
        manifest=manifest,
    )
    project_place = project_dir / "GeneratedGame.rbxlx"
    manifest["project_dir"] = str(project_dir)
    manifest["project_place"] = str(project_place)

    manifest_path = place_path.with_suffix(".place.json")
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (project_dir / "metadata.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    if not validation.valid:
        raise RuntimeError(
            "Generated place failed local validation: "
            + "; ".join(validation.errors)
        )

    return GeneratedPlace(
        build_id=build_id,
        source_name=source_name,
        place_path=str(project_place),
        manifest_path=str(manifest_path),
        status="GENERATED",
        message="Roblox XML place generated successfully.",
    )


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
    versions_dir = local_app_data / "Roblox" / "Versions"
    candidates = [
        *versions_dir.glob("*/RobloxStudioBeta.exe"),
        *versions_dir.glob("*/RobloxStudio.exe"),
    ]
    candidates = [path for path in candidates if path.exists()]
    if not candidates:
        raise FileNotFoundError(
            "Roblox Studio was not found. Install Studio or set "
            "ROBLOX_STUDIO_PATH in .env."
        )
    return max(
        candidates,
        key=lambda path: path.stat().st_mtime,
    ).resolve()


def open_place_in_studio(
    place_path: str | Path,
) -> tuple[int | None, list[str]]:
    place = Path(place_path).resolve()
    validation = validate_place_file(place)

    if not validation.valid:
        raise RuntimeError(
            "Refusing to open invalid generated place: "
            + "; ".join(validation.errors)
        )

    attempts: list[str] = []

    # Most reliable on Windows: ask the shell to open the actual .rbxlx file.
    # This uses the user's current file association.
    if os.name == "nt":
        try:
            _windows_open_file(place)
            return None, ["os.startfile", str(place)]
        except OSError as exc:
            attempts.append(f"Windows file association failed: {exc}")

    # Official simple form: pass the local place path as the first positional
    # argument to Roblox Studio.
    studio = find_roblox_studio()
    try:
        return _launch_studio_positional(studio, place)
    except OSError as exc:
        attempts.append(f"Studio positional launch failed: {exc}")

    # Official explicit EditFile fallback.
    command = [
        str(studio),
        "--task",
        "EditFile",
        "--localPlaceFile",
        str(place),
    ]
    try:
        process = subprocess.Popen(
            command,
            cwd=str(place.parent),
            creationflags=(
                subprocess.CREATE_NEW_PROCESS_GROUP
                if os.name == "nt"
                else 0
            ),
        )
        return process.pid, command
    except OSError as exc:
        attempts.append(f"Studio EditFile launch failed: {exc}")

    raise RuntimeError(" | ".join(attempts))

def generate_and_open(build_id: str | None = None) -> GeneratedPlace:
    result = generate_place(build_id)
    pid, _ = open_place_in_studio(result.place_path)
    result.studio_launched = True
    result.studio_pid = pid
    result.status = "GENERATED_AND_OPENED"
    result.message = (
        "Place generated and Roblox Studio launch requested."
    )
    return result


def open_generated_folder() -> Path:
    PROJECT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        os.startfile(str(PROJECT_OUTPUT_DIR))  # type: ignore[attr-defined]
    elif os.name == "posix":
        subprocess.Popen(["xdg-open", str(PROJECT_OUTPUT_DIR)])
    return PROJECT_OUTPUT_DIR


def list_generated_places(limit: int = 100) -> list[dict[str, Any]]:
    PLACE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []

    for path in PLACE_OUTPUT_DIR.glob("*.place.json"):
        try:
            data = _read_json(path)
            data["manifest_path"] = str(path)
            rows.append(data)
        except (OSError, json.JSONDecodeError):
            continue

    rows.sort(
        key=lambda item: float(item.get("generated_at") or 0),
        reverse=True,
    )
    return rows[: max(1, int(limit))]
