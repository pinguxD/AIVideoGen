from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .full_video_analyzer import BASE
from .world_planner import WorldPlan

TEMPLATE_DIR = BASE / "assets" / "roblox_templates"
TEMPLATE_PATH = TEMPLATE_DIR / "AIVideoGenBase.rbxlx"
OUTPUT_DIR = BASE / "outputs" / "creator_ai_v2"


@dataclass
class CompileResult:
    project_id: str
    source_name: str
    place_path: str
    project_dir: str
    valid: bool
    errors: list[str]
    warnings: list[str]


class Refs:
    def __init__(self, root: ET.Element) -> None:
        self.used = {item.attrib.get("referent", "") for item in root.findall(".//Item")}
        self.index = 0

    def next(self) -> str:
        while True:
            self.index += 1
            value = f"RBXMAP{self.index:X}"
            if value not in self.used:
                self.used.add(value)
                return value


def _prop(parent: ET.Element, tag: str, name: str, value: Any) -> None:
    node = ET.SubElement(parent, tag, {"name": name})
    node.text = ("true" if bool(value) else "false") if tag == "bool" else str(value)


def _vec(parent: ET.Element, name: str, values: tuple[float, float, float]) -> None:
    node = ET.SubElement(parent, "Vector3", {"name": name})
    for tag, value in zip(("X", "Y", "Z"), values):
        ET.SubElement(node, tag).text = str(value)


def _cframe(parent: ET.Element, name: str, values: tuple[float, float, float]) -> None:
    node = ET.SubElement(parent, "CoordinateFrame", {"name": name})
    for tag, value in zip(("X", "Y", "Z"), values):
        ET.SubElement(node, tag).text = str(value)
    for tag, value in {"R00":1,"R01":0,"R02":0,"R10":0,"R11":1,"R12":0,"R20":0,"R21":0,"R22":1}.items():
        ET.SubElement(node, tag).text = str(value)


def _color(rgb: tuple[int, int, int]) -> int:
    r, g, b = [max(0, min(255, int(value))) for value in rgb]
    return (255 << 24) | (r << 16) | (g << 8) | b


def _item(parent: ET.Element, refs: Refs, class_name: str, name: str) -> tuple[ET.Element, ET.Element]:
    item = ET.SubElement(parent, "Item", {"class": class_name, "referent": refs.next()})
    properties = ET.SubElement(item, "Properties")
    _prop(properties, "string", "Name", name)
    return item, properties


def _name(item: ET.Element) -> str:
    node = item.find("./Properties/string[@name='Name']")
    return node.text if node is not None and node.text else ""


def _service(root: ET.Element, class_name: str) -> ET.Element:
    for item in root.findall("./Item"):
        if item.attrib.get("class") == class_name:
            return item
    raise ValueError(f"Template missing service: {class_name}")


def _remove(parent: ET.Element, name: str) -> None:
    for child in list(parent.findall("./Item")):
        if _name(child) == name:
            parent.remove(child)


def _part(parent: ET.Element, refs: Refs, name: str, size: tuple[float,float,float], position: tuple[float,float,float], rgb: tuple[int,int,int], class_name: str = "Part", material: int = 256, transparency: float = 0.0, can_collide: bool = True) -> ET.Element:
    item, props = _item(parent, refs, class_name, name)
    _prop(props, "bool", "Anchored", True)
    _prop(props, "bool", "CanCollide", can_collide)
    _cframe(props, "CFrame", position)
    _vec(props, "size", size)
    _prop(props, "Color3uint8", "Color3uint8", _color(rgb))
    _prop(props, "token", "Material", material)
    _prop(props, "float", "Transparency", transparency)
    return item


def _script(parent: ET.Element, refs: Refs, name: str, source: str, class_name: str = "ModuleScript") -> ET.Element:
    item, props = _item(parent, refs, class_name, name)
    _prop(props, "bool", "Disabled", False)
    _prop(props, "ProtectedString", "Source", source)
    return item


def _bridge(parent: ET.Element, refs: Refs, left: Any, right: Any, width: float, color: tuple[int,int,int]) -> None:
    left_front = left.center[2] + left.size[2] / 2.0
    right_back = right.center[2] - right.size[2] / 2.0
    length = max(1.0, right_back - left_front)
    _part(parent, refs, f"Bridge_{left.platform_id}_{right.platform_id}", (max(4.0, width), 0.8, length), ((left.center[0] + right.center[0]) / 2, min(left.center[1], right.center[1]), (left_front + right_back) / 2), color)


def _railing(parent: ET.Element, refs: Refs, platform: Any, color: tuple[int,int,int]) -> None:
    cx, cy, cz = platform.center
    sx, _, sz = platform.size
    for side, x in (("Left", cx - sx / 2 + 0.3), ("Right", cx + sx / 2 - 0.3)):
        _part(parent, refs, f"{platform.platform_id}_{side}Railing", (0.45, 4.0, sz), (x, cy + 2.0, cz), color)


def _prop_model(parent: ET.Element, refs: Refs, spec: dict[str, Any], palette: list[tuple[int,int,int]]) -> None:
    prop_type = str(spec.get("type") or "prop")
    x, y, z = [float(value) for value in spec.get("position", [0, 1, 0])]
    color = tuple(spec.get("color") or palette[1])
    if prop_type == "hospital_bed":
        _part(parent, refs, "HospitalBedBase", (7, 1, 3), (x, y, z), (225, 228, 235))
        _part(parent, refs, "HospitalBedMattress", (6.5, 0.6, 2.7), (x, y + 0.8, z), (245, 250, 255))
        _part(parent, refs, "HospitalBedHead", (0.4, 3, 3), (x - 3.3, y + 1.5, z), (150, 185, 210))
    elif prop_type == "reception_desk":
        _part(parent, refs, "ReceptionDesk", (12, 4, 3), (x, y, z), (100, 150, 190))
        _part(parent, refs, "ReceptionTop", (12.8, 0.4, 3.6), (x, y + 2.2, z), (230, 235, 240))
    elif prop_type == "accent_column":
        _part(parent, refs, "AccentColumn", (2, 8, 2), (x, y, z), color)
        _part(parent, refs, "AccentGlow", (3.2, 0.5, 3.2), (x, y + 4.2, z), palette[2])
    else:
        _part(parent, refs, prop_type, (4, 4, 4), (x, y, z), color)


def _gameplay_source(plan: WorldPlan) -> str:
    plan_json = json.dumps(asdict(plan), ensure_ascii=False)
    return '''local Players = game:GetService("Players")
local TweenService = game:GetService("TweenService")
local M = {}
local PLAN = %s

local function scaleCharacter(humanoid, target)
    for _, name in ipairs({"BodyHeightScale","BodyWidthScale","BodyDepthScale","HeadScale"}) do
        local value = humanoid:FindFirstChild(name)
        if value and value:IsA("NumberValue") then
            TweenService:Create(value, TweenInfo.new(1.2), {Value = target}):Play()
        end
    end
end

function M.Start()
    local player = Players.LocalPlayer
    local character = player.Character or player.CharacterAdded:Wait()
    local humanoid = character:WaitForChild("Humanoid")
    local root = character:WaitForChild("HumanoidRootPart")
    for _, spec in ipairs(PLAN.gameplay_specs or {}) do
        task.spawn(function()
            task.wait(tonumber(spec.start) or 0)
            local props = spec.properties or {}
            local target = props.target_position
            if spec.action == "walk" and target then
                humanoid.WalkSpeed = 16
                humanoid:MoveTo(Vector3.new(target[1], target[2], target[3]))
            elseif spec.action == "jump" then
                if target then humanoid:MoveTo(Vector3.new(target[1], target[2], target[3])) end
                task.wait(0.6)
                humanoid.Jump = true
            elseif spec.action == "grow" then
                scaleCharacter(humanoid, tonumber(props.target_scale) or 2)
            elseif spec.action == "shrink" then
                scaleCharacter(humanoid, tonumber(props.target_scale) or 0.6)
            elseif spec.action == "turn" then
                root.CFrame = root.CFrame * CFrame.Angles(0, math.rad(90), 0)
            end
        end)
    end
end
return M''' % plan_json


def _camera_source(plan: WorldPlan) -> str:
    specs = json.dumps(plan.camera_specs, ensure_ascii=False)
    return '''local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")
local M = {}
local SPECS = %s
function M.Start()
    local player = Players.LocalPlayer
    local character = player.Character or player.CharacterAdded:Wait()
    local root = character:WaitForChild("HumanoidRootPart")
    local camera = workspace.CurrentCamera
    camera.CameraType = Enum.CameraType.Scriptable
    RunService.RenderStepped:Connect(function()
        if not root.Parent then return end
        local target = root.Position + Vector3.new(0, 2.5, 0)
        local position = root.Position - root.CFrame.LookVector * 11 + Vector3.new(0, 4.5, 0)
        camera.CFrame = CFrame.lookAt(position, target)
    end)
    local pattern = SPECS[2]
    if pattern and pattern.interval and pattern.occurrences then
        task.spawn(function()
            for _ = 1, pattern.occurrences do
                task.wait(pattern.interval)
                local original = camera.FieldOfView
                TweenService:Create(camera, TweenInfo.new(0.08), {FieldOfView = math.max(38, original - 10)}):Play()
                task.wait(0.10)
                TweenService:Create(camera, TweenInfo.new(0.12), {FieldOfView = original}):Play()
            end
        end)
    end
end
return M''' % specs


def _npc_source(plan: WorldPlan) -> str:
    data = json.dumps(plan.npc_specs, ensure_ascii=False)
    return '''local Players = game:GetService("Players")
local M = {}
local SPECS = %s
function M.Start(folder)
    for index, spec in ipairs(SPECS) do
        local model = Instance.new("Model")
        model.Name = (spec.type or "NPC") .. index
        model.Parent = folder
        local root = Instance.new("Part")
        root.Name = "HumanoidRootPart"
        root.Size = Vector3.new(2, 2, 1)
        local position = spec.position or {0, 2, 20}
        root.Position = Vector3.new(position[1], position[2], position[3])
        root.Parent = model
        local head = Instance.new("Part")
        head.Name = "Head"
        head.Shape = Enum.PartType.Ball
        head.Size = Vector3.new(2, 2, 2)
        head.Position = root.Position + Vector3.new(0, 2, 0)
        head.Parent = model
        local humanoid = Instance.new("Humanoid")
        humanoid.WalkSpeed = spec.speed or 12
        humanoid.Parent = model
        model.PrimaryPart = root
        if spec.behavior == "chase" then
            task.spawn(function()
                while model.Parent do
                    task.wait(0.25)
                    local player = Players:GetPlayers()[1]
                    local target = player and player.Character and player.Character:FindFirstChild("HumanoidRootPart")
                    if target then humanoid:MoveTo(target.Position) end
                end
            end)
        end
    end
end
return M''' % data


def _bootstrap() -> str:
    return '''local ReplicatedStorage = game:GetService("ReplicatedStorage")
local package = ReplicatedStorage:WaitForChild("CreatorAIV2Package")
require(package:WaitForChild("GameplayCompiler")).Start()
require(package:WaitForChild("CameraDirector")).Start()
require(package:WaitForChild("NPCDirector")).Start(workspace:WaitForChild("CreatorAIV2Generated"))'''


def _validate(path: Path) -> dict[str, Any]:
    root = ET.parse(path).getroot()
    names = {_name(item) for item in root.findall(".//Item")}
    errors = [f"Missing {required}" for required in ("CreatorAIV2Generated", "CreatorAIV2Package", "GeneratedScene", "GeneratedSpawn") if required not in names]
    return {"valid": not errors, "errors": errors, "warnings": [], "size_bytes": path.stat().st_size}


def compile_world(source_name: str, plan: WorldPlan, template_path: str | Path = TEMPLATE_PATH) -> CompileResult:
    template = Path(template_path)
    if not template.exists():
        raise FileNotFoundError("Upload a blank Baseplate .rbxlx on Creator AI v2 first.")
    tree = ET.parse(template)
    root = tree.getroot()
    refs = Refs(root)
    workspace, replicated_storage, starter_player = _service(root, "Workspace"), _service(root, "ReplicatedStorage"), _service(root, "StarterPlayer")
    _remove(workspace, "CreatorAIV2Generated")
    generated, _ = _item(workspace, refs, "Folder", "CreatorAIV2Generated")

    for platform in plan.platforms:
        _part(generated, refs, platform.platform_id, platform.size, platform.center, platform.color)
        if platform.railing:
            _railing(generated, refs, platform, plan.palette[3])
    lookup = {platform.platform_id: platform for platform in plan.platforms}
    for connection in plan.connections:
        if connection.kind == "walk_bridge" and connection.from_id in lookup and connection.to_id in lookup:
            _bridge(generated, refs, lookup[connection.from_id], lookup[connection.to_id], connection.width, plan.palette[0])
    for wall in plan.walls:
        _part(generated, refs, wall.wall_id, wall.size, wall.center, wall.color)
    for spec in plan.props:
        _prop_model(generated, refs, spec, plan.palette)
    for hazard in plan.hazards:
        x, y, z = hazard.get("position", [0, 1, 0])
        sx, sy, sz = hazard.get("size", [8, 1, 8])
        _part(generated, refs, "KillBlock", (sx, sy, sz), (x, y, z), (255, 55, 55))
    spawn = plan.player_path[0] if plan.player_path else (0, 3, 0)
    _part(generated, refs, "GeneratedSpawn", (8, 1, 8), (spawn[0], max(1.0, spawn[1] - 2.0), spawn[2]), (80, 220, 120), "SpawnLocation")

    _remove(replicated_storage, "CreatorAIV2Package")
    package, _ = _item(replicated_storage, refs, "Folder", "CreatorAIV2Package")
    _script(package, refs, "GameplayCompiler", _gameplay_source(plan))
    _script(package, refs, "CameraDirector", _camera_source(plan))
    _script(package, refs, "NPCDirector", _npc_source(plan))

    starter_scripts = next((child for child in starter_player.findall("./Item") if child.attrib.get("class") == "StarterPlayerScripts" or _name(child) == "StarterPlayerScripts"), None)
    if starter_scripts is None:
        starter_scripts, _ = _item(starter_player, refs, "StarterPlayerScripts", "StarterPlayerScripts")
    _remove(starter_scripts, "GeneratedScene")
    _script(starter_scripts, refs, "GeneratedScene", _bootstrap(), "LocalScript")

    project_id = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in Path(source_name).stem)
    project_dir = OUTPUT_DIR / f"{safe}_{project_id}"
    project_dir.mkdir(parents=True, exist_ok=True)
    place_path = project_dir / "GeneratedGame.rbxlx"
    ET.indent(tree, space="  ")
    tree.write(place_path, encoding="utf-8", xml_declaration=True)
    result = _validate(place_path)
    (project_dir / "world_plan.json").write_text(json.dumps(asdict(plan), indent=2, ensure_ascii=False), encoding="utf-8")
    (project_dir / "validation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return CompileResult(project_id, source_name, str(place_path), str(project_dir), result["valid"], result["errors"], result["warnings"])


def install_template(upload: Any) -> Path:
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    upload.save(TEMPLATE_PATH)
    ET.parse(TEMPLATE_PATH)
    return TEMPLATE_PATH


def open_place(path: str | Path) -> None:
    place = Path(path)
    if os.name == "nt":
        os.startfile(str(place))  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", str(place)])
