from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .full_video_analyzer import BASE

TEMPLATE_DIR = BASE / "assets" / "roblox_templates"
TEMPLATE_PATH = TEMPLATE_DIR / "AIVideoGenBase.rbxlx"
OUTPUT_DIR = BASE / "outputs" / "creator_ai_v2"


@dataclass
class CompileResult:
    project_id: str
    source_name: str
    template_path: str
    place_path: str
    project_dir: str
    validation_path: str
    valid: bool
    errors: list[str]
    warnings: list[str]


class Referents:
    def __init__(self, existing_root: ET.Element) -> None:
        self.used = {
            item.attrib.get("referent", "")
            for item in existing_root.findall(".//Item")
        }
        self.counter = 0

    def next(self) -> str:
        while True:
            self.counter += 1
            value = f"RBXAI{self.counter:X}"
            if value not in self.used:
                self.used.add(value)
                return value


def _property(parent: ET.Element, tag: str, name: str, value: Any) -> ET.Element:
    node = ET.SubElement(parent, tag, {"name": name})
    if tag == "bool":
        node.text = "true" if bool(value) else "false"
    else:
        node.text = str(value)
    return node


def _vector3(parent: ET.Element, name: str, xyz: tuple[float, float, float]) -> ET.Element:
    node = ET.SubElement(parent, "Vector3", {"name": name})
    for tag, value in zip(("X", "Y", "Z"), xyz):
        ET.SubElement(node, tag).text = str(value)
    return node


def _cframe(parent: ET.Element, name: str, xyz: tuple[float, float, float]) -> ET.Element:
    node = ET.SubElement(parent, "CoordinateFrame", {"name": name})
    for tag, value in zip(("X", "Y", "Z"), xyz):
        ET.SubElement(node, tag).text = str(value)
    rotation = {
        "R00": 1, "R01": 0, "R02": 0,
        "R10": 0, "R11": 1, "R12": 0,
        "R20": 0, "R21": 0, "R22": 1,
    }
    for tag, value in rotation.items():
        ET.SubElement(node, tag).text = str(value)
    return node


def _color_uint8(rgb: tuple[int, int, int]) -> int:
    r, g, b = [max(0, min(255, int(value))) for value in rgb]
    return (255 << 24) | (r << 16) | (g << 8) | b


def _item(
    parent: ET.Element,
    refs: Referents,
    class_name: str,
    name: str,
) -> tuple[ET.Element, ET.Element]:
    item = ET.SubElement(
        parent,
        "Item",
        {
            "class": class_name,
            "referent": refs.next(),
        },
    )
    properties = ET.SubElement(item, "Properties")
    _property(properties, "string", "Name", name)
    return item, properties


def _find_service(root: ET.Element, class_name: str) -> ET.Element:
    for item in root.findall("./Item"):
        if item.attrib.get("class") == class_name:
            return item
    raise ValueError(
        f"Template is missing required Roblox service: {class_name}"
    )


def _name_of(item: ET.Element) -> str:
    node = item.find("./Properties/string[@name='Name']")
    return node.text if node is not None and node.text else ""


def _remove_named_child(parent: ET.Element, name: str) -> None:
    for child in list(parent.findall("./Item")):
        if _name_of(child) == name:
            parent.remove(child)


def _add_part(
    parent: ET.Element,
    refs: Referents,
    name: str,
    size: tuple[float, float, float],
    position: tuple[float, float, float],
    rgb: tuple[int, int, int],
    class_name: str = "Part",
) -> ET.Element:
    item, props = _item(parent, refs, class_name, name)
    _property(props, "bool", "Anchored", True)
    _property(props, "bool", "CanCollide", True)
    _cframe(props, "CFrame", position)
    _vector3(props, "size", size)
    _property(props, "Color3uint8", "Color3uint8", _color_uint8(rgb))
    _property(props, "token", "Material", 256)
    _property(props, "float", "Transparency", 0)
    return item


def _add_module(
    parent: ET.Element,
    refs: Referents,
    name: str,
    source: str,
) -> ET.Element:
    item, props = _item(parent, refs, "ModuleScript", name)
    _property(props, "bool", "Disabled", False)
    _property(props, "ProtectedString", "Source", source)
    return item


def _add_local_script(
    parent: ET.Element,
    refs: Referents,
    name: str,
    source: str,
) -> ET.Element:
    item, props = _item(parent, refs, "LocalScript", name)
    _property(props, "bool", "Disabled", False)
    _property(props, "ProtectedString", "Source", source)
    return item


def _environment(
    folder: ET.Element,
    refs: Referents,
    blueprint: dict[str, Any],
) -> None:
    graph = blueprint.get("environment_graph") or {}
    scene_type = str(graph.get("scene_type") or "simple_platform")

    if scene_type == "simple_obby":
        for index in range(10):
            _add_part(
                folder,
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
    elif scene_type == "hospital":
        _add_part(
            folder,
            refs,
            "HospitalFloor",
            (60, 1, 50),
            (0, 0, 0),
            (225, 230, 235),
        )
        _add_part(
            folder,
            refs,
            "HospitalBackWall",
            (60, 18, 1),
            (0, 9, 25),
            (185, 210, 225),
        )
        _add_part(
            folder,
            refs,
            "ReceptionDesk",
            (14, 4, 3),
            (0, 2, 8),
            (110, 160, 195),
        )
    elif scene_type == "horror_corridor":
        _add_part(
            folder,
            refs,
            "CorridorFloor",
            (18, 1, 80),
            (0, 0, 0),
            (42, 42, 42),
        )
        _add_part(
            folder,
            refs,
            "LeftWall",
            (1, 18, 80),
            (-9, 9, 0),
            (30, 30, 30),
        )
        _add_part(
            folder,
            refs,
            "RightWall",
            (1, 18, 80),
            (9, 9, 0),
            (30, 30, 30),
        )
    else:
        _add_part(
            folder,
            refs,
            "GeneratedBaseplate",
            (80, 1, 80),
            (0, 0, 0),
            (210, 210, 210),
        )

    _add_part(
        folder,
        refs,
        "GeneratedSpawn",
        (8, 1, 8),
        (0, 1, 0),
        (90, 200, 120),
        class_name="SpawnLocation",
    )


def _load_package_files(scene_package_dir: Path) -> tuple[dict[str, Any], dict[str, str]]:
    blueprint_path = scene_package_dir / "blueprint" / "roblox_brain.json"
    if not blueprint_path.exists():
        raise FileNotFoundError(
            f"Roblox Brain blueprint is missing: {blueprint_path}"
        )
    blueprint = json.loads(blueprint_path.read_text(encoding="utf-8"))

    lua_files: dict[str, str] = {}
    for suffix in ("*.lua", "*.luau"):
        for path in scene_package_dir.rglob(suffix):
            relative = str(
                path.relative_to(scene_package_dir)
            ).replace("\\", "/")
            lua_files[relative] = path.read_text(encoding="utf-8")

    return blueprint, lua_files


def _set_lighting(lighting: ET.Element, blueprint: dict[str, Any]) -> None:
    props = lighting.find("./Properties")
    if props is None:
        props = ET.SubElement(lighting, "Properties")

    preset = str(blueprint.get("lighting") or "bright_cartoon")
    values = {
        "dark_horror": (1.0, 1.0),
        "clean_indoor": (2.5, 13.0),
        "bright_cartoon": (3.0, 14.0),
    }
    brightness, clock_time = values.get(
        preset,
        values["bright_cartoon"],
    )

    for property_name, value in (
        ("Brightness", brightness),
        ("ClockTime", clock_time),
    ):
        node = props.find(f"./float[@name='{property_name}']")
        if node is None:
            node = ET.SubElement(
                props,
                "float",
                {"name": property_name},
            )
        node.text = str(value)


def validate_compiled_place(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        return {
            "valid": False,
            "errors": [f"XML parse failed: {exc}"],
            "warnings": [],
        }

    if root.tag != "roblox":
        errors.append("Root element is not <roblox>.")

    required_classes = {
        "Workspace",
        "ReplicatedStorage",
        "StarterPlayer",
        "Lighting",
    }
    present_classes = {
        item.attrib.get("class", "")
        for item in root.findall("./Item")
    }
    for required in sorted(required_classes):
        if required not in present_classes:
            errors.append(f"Missing required service: {required}")

    names = {
        _name_of(item)
        for item in root.findall(".//Item")
    }
    for required_name in (
        "AIVideoGenGenerated",
        "AIVideoGenPackage",
        "Modules",
        "GeneratedScene",
    ):
        if required_name not in names:
            errors.append(f"Missing generated object: {required_name}")

    size_bytes = path.stat().st_size
    if size_bytes > 104_857_600:
        errors.append("Compiled place exceeds 100 MB.")
    if size_bytes < 2_000:
        warnings.append("Compiled place is unusually small.")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "size_bytes": size_bytes,
    }


def compile_from_template(
    source_name: str,
    scene_package_dir: str | Path,
    template_path: str | Path = TEMPLATE_PATH,
) -> CompileResult:
    template = Path(template_path)
    if not template.exists():
        raise FileNotFoundError(
            "A valid Roblox template has not been configured. "
            "Save a blank Baseplate from Studio as an .rbxlx file, "
            "then upload it on the Creator AI v2 page."
        )

    scene_package = Path(scene_package_dir)
    if not scene_package.exists():
        raise FileNotFoundError(
            f"Scene package directory does not exist: {scene_package}"
        )

    blueprint, lua_files = _load_package_files(scene_package)

    tree = ET.parse(template)
    root = tree.getroot()
    refs = Referents(root)

    workspace = _find_service(root, "Workspace")
    replicated_storage = _find_service(root, "ReplicatedStorage")
    starter_player = _find_service(root, "StarterPlayer")
    lighting = _find_service(root, "Lighting")

    _remove_named_child(workspace, "AIVideoGenGenerated")
    generated, _ = _item(
        workspace,
        refs,
        "Folder",
        "AIVideoGenGenerated",
    )
    _environment(generated, refs, blueprint)

    _remove_named_child(replicated_storage, "AIVideoGenPackage")
    package, _ = _item(
        replicated_storage,
        refs,
        "Folder",
        "AIVideoGenPackage",
    )

    blueprint_value, blueprint_props = _item(
        package,
        refs,
        "StringValue",
        "BlueprintJSON",
    )
    _property(
        blueprint_props,
        "string",
        "Value",
        json.dumps(
            blueprint,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    )

    modules, _ = _item(package, refs, "Folder", "Modules")
    mechanics, _ = _item(modules, refs, "Folder", "Mechanics")

    for relative, source in sorted(lua_files.items()):
        if not relative.startswith("modules/"):
            continue
        name = Path(relative).stem
        parent = (
            mechanics
            if relative.startswith("modules/mechanics/")
            else modules
        )
        _add_module(parent, refs, name, source)

    starter_player_scripts = None
    for child in starter_player.findall("./Item"):
        if (
            child.attrib.get("class") == "StarterPlayerScripts"
            or _name_of(child) == "StarterPlayerScripts"
        ):
            starter_player_scripts = child
            break

    if starter_player_scripts is None:
        starter_player_scripts, _ = _item(
            starter_player,
            refs,
            "StarterPlayerScripts",
            "StarterPlayerScripts",
        )

    _remove_named_child(
        starter_player_scripts,
        "GeneratedScene",
    )
    client_source = lua_files.get(
        "scripts/GeneratedScene.client.lua",
        "warn('[Creator AI v2] GeneratedScene source missing.')",
    )
    _add_local_script(
        starter_player_scripts,
        refs,
        "GeneratedScene",
        client_source,
    )

    _set_lighting(lighting, blueprint)

    project_id = (
        f"{int(time.time())}_"
        f"{uuid.uuid4().hex[:8]}"
    )
    safe_name = "".join(
        character
        if character.isalnum() or character in "-_"
        else "_"
        for character in Path(source_name).stem
    ).strip("_") or "GeneratedGame"

    project_dir = OUTPUT_DIR / f"{safe_name}_{project_id}"
    project_dir.mkdir(parents=True, exist_ok=True)
    place_path = project_dir / "GeneratedGame.rbxlx"

    ET.indent(tree, space="  ")
    tree.write(
        place_path,
        encoding="utf-8",
        xml_declaration=True,
    )

    validation = validate_compiled_place(place_path)
    validation_path = project_dir / "validation.json"
    validation_path.write_text(
        json.dumps(validation, indent=2),
        encoding="utf-8",
    )

    (project_dir / "blueprint.json").write_text(
        json.dumps(
            blueprint,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    shutil.copytree(
        scene_package,
        project_dir / "scene_package",
        dirs_exist_ok=True,
    )
    for folder in ("assets", "sounds", "thumbnails"):
        (project_dir / folder).mkdir(exist_ok=True)

    metadata = {
        "project_id": project_id,
        "source_name": source_name,
        "template_path": str(template),
        "place_path": str(place_path),
        "scene_package_dir": str(scene_package),
        "validation": validation,
        "generated_at": time.time(),
    }
    (project_dir / "metadata.json").write_text(
        json.dumps(
            metadata,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return CompileResult(
        project_id=project_id,
        source_name=source_name,
        template_path=str(template),
        place_path=str(place_path),
        project_dir=str(project_dir),
        validation_path=str(validation_path),
        valid=bool(validation.get("valid")),
        errors=list(validation.get("errors") or []),
        warnings=list(validation.get("warnings") or []),
    )


def install_template(uploaded_file) -> Path:
    filename = str(
        getattr(uploaded_file, "filename", "") or ""
    )
    if not filename.lower().endswith(".rbxlx"):
        raise ValueError("The template must be an .rbxlx file.")

    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    uploaded_file.save(TEMPLATE_PATH)

    try:
        root = ET.parse(TEMPLATE_PATH).getroot()
    except ET.ParseError as exc:
        TEMPLATE_PATH.unlink(missing_ok=True)
        raise ValueError(
            f"The uploaded file is not valid XML: {exc}"
        ) from exc

    required = {
        item.attrib.get("class", "")
        for item in root.findall("./Item")
    }
    missing = {
        "Workspace",
        "ReplicatedStorage",
        "StarterPlayer",
        "Lighting",
    } - required
    if missing:
        TEMPLATE_PATH.unlink(missing_ok=True)
        raise ValueError(
            "The template is missing Roblox services: "
            + ", ".join(sorted(missing))
        )

    return TEMPLATE_PATH


def open_project(place_path: str | Path) -> None:
    place = Path(place_path)
    if not place.exists():
        raise FileNotFoundError(place)

    if os.name == "nt":
        os.startfile(str(place))  # type: ignore[attr-defined]
        return

    subprocess.Popen(["xdg-open", str(place)])


def open_project_folder(project_dir: str | Path) -> None:
    folder = Path(project_dir)
    if os.name == "nt":
        os.startfile(str(folder))  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", str(folder)])
