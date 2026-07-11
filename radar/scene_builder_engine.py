from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from .full_video_analyzer import BASE
from .roblox_brain import build_roblox_brain_plan, load_roblox_brain_plan

OUTPUT_DIR = BASE / "outputs" / "scene_builder"


@dataclass
class Artifact:
    kind: str
    name: str
    path: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BuilderResult:
    builder_id: str
    phase: str
    status: str
    message: str
    artifacts: list[Artifact] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class BuildManifest:
    source_name: str
    build_id: str
    status: str
    package_dir: str
    results: list[BuilderResult]
    artifacts: list[Artifact]
    missing_builders: list[str]
    warnings: list[str]
    created_at: float

    def save(self) -> Path:
        path = OUTPUT_DIR / self.build_id / "build_manifest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path


def _safe_name(value: str) -> str:
    return "".join(
        c if c.isalnum() or c in "-_" else "_"
        for c in str(value)
    ).strip("_") or "item"


def _write_text(package_dir: Path, relative: str, content: str) -> Path:
    path = package_dir / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _write_json(package_dir: Path, relative: str, data: Any) -> Path:
    path = package_dir / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def _lua(value: Any, indent: int = 0) -> str:
    pad = " " * indent
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        rows = [
            " " * (indent + 4) + _lua(item, indent + 4)
            for item in value
        ]
        return "{\n" + ",\n".join(rows) + "\n" + pad + "}"
    if isinstance(value, dict):
        rows = []
        for key, item in value.items():
            rendered = (
                str(key)
                if str(key).isidentifier()
                else "[" + json.dumps(str(key)) + "]"
            )
            rows.append(
                " " * (indent + 4)
                + rendered
                + " = "
                + _lua(item, indent + 4)
            )
        return "{\n" + ",\n".join(rows) + "\n" + pad + "}"
    return json.dumps(str(value))


def _artifact(
    package_dir: Path,
    kind: str,
    name: str,
    path: Path,
    **metadata: Any,
) -> Artifact:
    return Artifact(
        kind=kind,
        name=name,
        path=str(path.relative_to(package_dir)).replace("\\", "/"),
        metadata=metadata,
    )


def _environment_builder(
    command: dict[str, Any],
    blueprint: dict[str, Any],
    package_dir: Path,
) -> BuilderResult:
    spec = (
        command.get("properties")
        or blueprint.get("environment_graph")
        or {}
    )
    code = (
        "local M = {}\n"
        f"local SPEC = {_lua(spec)}\n"
        "local function createPart(parent,name,size,pos,color)\n"
        "    local p=Instance.new('Part')\n"
        "    p.Name=name; p.Anchored=true; p.Size=size; p.Position=pos\n"
        "    p.Color=color or Color3.fromRGB(210,210,210); p.Parent=parent\n"
        "    return p\n"
        "end\n"
        "function M.Build()\n"
        "    local old=workspace:FindFirstChild('AIVideoGenGenerated')\n"
        "    if old then old:Destroy() end\n"
        "    local root=Instance.new('Folder')\n"
        "    root.Name='AIVideoGenGenerated'; root.Parent=workspace\n"
        "    local t=SPEC.scene_type or 'simple_platform'\n"
        "    if t=='simple_obby' then\n"
        "        for i=1,10 do\n"
        "            createPart(root,'Platform'..i,Vector3.new(8,1,8),"
        "Vector3.new((i-1)*10,(i%3)*2,0),Color3.fromHSV(i/10,.7,1))\n"
        "        end\n"
        "    elseif t=='hospital' then\n"
        "        createPart(root,'Floor',Vector3.new(60,1,50),Vector3.new(0,0,0),Color3.fromRGB(225,230,235))\n"
        "        createPart(root,'Wall',Vector3.new(60,18,1),Vector3.new(0,9,25),Color3.fromRGB(185,210,225))\n"
        "    else\n"
        "        createPart(root,'Baseplate',Vector3.new(80,1,80),Vector3.new(0,0,0))\n"
        "    end\n"
        "    local spawn=Instance.new('SpawnLocation')\n"
        "    spawn.Name='GeneratedSpawn'; spawn.Position=Vector3.new(0,1,0); spawn.Parent=root\n"
        "    return root\n"
        "end\n"
        "return M\n"
    )
    path = _write_text(
        package_dir,
        "modules/EnvironmentBuilder.lua",
        code,
    )
    return BuilderResult(
        "scene.environment_graph.v1",
        "environment",
        "BUILT",
        "Environment module generated.",
        [_artifact(package_dir, "luau_module", "EnvironmentBuilder", path)],
    )


def _character_builder(
    command: dict[str, Any],
    blueprint: dict[str, Any],
    package_dir: Path,
) -> BuilderResult:
    spec = (
        command.get("properties")
        or blueprint.get("character_state")
        or {}
    )
    code = (
        "local M = {}\n"
        f"local SPEC = {_lua(spec)}\n"
        "function M.Configure(character)\n"
        "    local h=character:WaitForChild('Humanoid')\n"
        "    local scale=tonumber(SPEC.scale) or 1\n"
        "    for _,n in ipairs({'BodyHeightScale','BodyWidthScale','BodyDepthScale','HeadScale'}) do\n"
        "        local v=h:FindFirstChild(n)\n"
        "        if v and v:IsA('NumberValue') then v.Value=scale end\n"
        "    end\n"
        "    h.Health=math.min(h.MaxHealth,tonumber(SPEC.health) or 100)\n"
        "    return h\n"
        "end\n"
        "return M\n"
    )
    path = _write_text(
        package_dir,
        "modules/CharacterBuilder.lua",
        code,
    )
    return BuilderResult(
        "character.spawn_r15.v1",
        "character",
        "BUILT",
        "Character module generated.",
        [_artifact(package_dir, "luau_module", "CharacterBuilder", path)],
    )


def _mechanic_builder(
    command: dict[str, Any],
    blueprint: dict[str, Any],
    package_dir: Path,
) -> BuilderResult:
    builder_id = str(command.get("builder_id") or "")
    action = str(command.get("command") or "")
    if not action or action.startswith("mechanic."):
        parts = builder_id.split(".")
        action = parts[1] if len(parts) > 1 else "unknown"

    properties = command.get("properties") or {}
    module_name = "Mechanic_" + _safe_name(action)

    handlers = {
        "walk": (
            "h.WalkSpeed=tonumber(p.walk_speed) or 16\n"
            "    h:MoveTo(r.Position+r.CFrame.LookVector*((tonumber(c.duration) or 2)*h.WalkSpeed*.7))"
        ),
        "jump": (
            "h.JumpPower=tonumber(p.jump_power) or 50\n"
            "    h.Jump=true"
        ),
        "grow": (
            "local t=tonumber(p.target_scale) or 2\n"
            "    for _,n in ipairs({'BodyHeightScale','BodyWidthScale','BodyDepthScale','HeadScale'}) do\n"
            "        local v=h:FindFirstChild(n); if v then v.Value=t end\n"
            "    end"
        ),
        "shrink": (
            "local t=tonumber(p.target_scale) or .5\n"
            "    for _,n in ipairs({'BodyHeightScale','BodyWidthScale','BodyDepthScale','HeadScale'}) do\n"
            "        local v=h:FindFirstChild(n); if v then v.Value=t end\n"
            "    end"
        ),
        "turn": (
            "r.CFrame=r.CFrame*CFrame.Angles(0,math.rad(tonumber(p.degrees) or 90),0)"
        ),
        "idle": "h:Move(Vector3.zero)",
    }
    body = handlers.get(
        action,
        f"warn('[AIVideoGen] Unimplemented mechanic: {action}')",
    )
    warnings = (
        []
        if action in handlers
        else [f"Mechanic '{action}' is currently a generated stub."]
    )

    code = (
        "local M = {}\n"
        f"local DEFAULTS = {_lua(properties)}\n"
        "function M.Run(c,p)\n"
        "    p=p or DEFAULTS\n"
        "    local h=c.humanoid; local r=c.root\n"
        "    if not h or not r then return end\n"
        f"    {body}\n"
        "end\n"
        "return M\n"
    )
    path = _write_text(
        package_dir,
        f"modules/mechanics/{module_name}.lua",
        code,
    )
    return BuilderResult(
        builder_id or f"mechanic.{action}.v1",
        "gameplay",
        "BUILT_WITH_WARNINGS" if warnings else "BUILT",
        f"Mechanic module generated: {action}.",
        [
            _artifact(
                package_dir,
                "luau_module",
                module_name,
                path,
                mechanic=action,
            )
        ],
        warnings,
    )


def _camera_builder(
    command: dict[str, Any],
    blueprint: dict[str, Any],
    package_dir: Path,
) -> BuilderResult:
    spec = {
        "camera": blueprint.get("camera") or {},
        "pattern": blueprint.get("camera_pattern") or {},
    }
    code = (
        "local RunService=game:GetService('RunService')\n"
        "local M={}\n"
        f"local SPEC={_lua(spec)}\n"
        "local connection=nil\n"
        "function M.Start(c)\n"
        "    local cam=workspace.CurrentCamera\n"
        "    cam.CameraType=Enum.CameraType.Scriptable\n"
        "    connection=RunService.RenderStepped:Connect(function()\n"
        "        local r=c.root; if not r or not r.Parent then return end\n"
        "        local pos=r.Position-r.CFrame.LookVector*9+Vector3.new(0,3,0)\n"
        "        cam.CFrame=CFrame.lookAt(pos,r.Position+Vector3.new(0,2,0))\n"
        "    end)\n"
        "    local p=SPEC.pattern or {}\n"
        "    local n=tonumber(p.occurrences) or 0\n"
        "    local interval=tonumber(p.average_interval)\n"
        "    if interval and interval>0 then\n"
        "        task.spawn(function()\n"
        "            for _=1,n do\n"
        "                task.wait(interval)\n"
        "                local f=cam.FieldOfView\n"
        "                cam.FieldOfView=math.max(35,f-10)\n"
        "                task.wait(.08)\n"
        "                cam.FieldOfView=f\n"
        "            end\n"
        "        end)\n"
        "    end\n"
        "end\n"
        "function M.Stop()\n"
        "    if connection then connection:Disconnect(); connection=nil end\n"
        "end\n"
        "return M\n"
    )
    path = _write_text(
        package_dir,
        "modules/CameraBuilder.lua",
        code,
    )
    return BuilderResult(
        "camera.controller.v1",
        "camera",
        "BUILT",
        "Camera controller generated.",
        [_artifact(package_dir, "luau_module", "CameraBuilder", path)],
    )


def _ui_builder(
    command: dict[str, Any],
    blueprint: dict[str, Any],
    package_dir: Path,
) -> BuilderResult:
    elements = [
        item.get("value")
        for item in blueprint.get("ui") or []
        if item.get("value") and item.get("value") != "none"
    ]
    code = (
        "local Players=game:GetService('Players')\n"
        "local M={}\n"
        f"local ELEMENTS={_lua(elements)}\n"
        "function M.Build()\n"
        "    local pg=Players.LocalPlayer:WaitForChild('PlayerGui')\n"
        "    local old=pg:FindFirstChild('AIVideoGenGui'); if old then old:Destroy() end\n"
        "    local gui=Instance.new('ScreenGui'); gui.Name='AIVideoGenGui'; gui.Parent=pg\n"
        "    local y=24\n"
        "    for _,element in ipairs(ELEMENTS) do\n"
        "        local label=Instance.new('TextLabel')\n"
        "        label.Name=element; label.Size=UDim2.fromOffset(300,60)\n"
        "        label.Position=UDim2.fromOffset(24,y)\n"
        "        label.BackgroundColor3=Color3.fromRGB(20,20,25)\n"
        "        label.TextColor3=Color3.new(1,1,1)\n"
        "        label.Font=Enum.Font.GothamBlack; label.TextScaled=true\n"
        "        label.Text=string.upper(element); label.Parent=gui\n"
        "        y+=70\n"
        "    end\n"
        "    return gui\n"
        "end\n"
        "return M\n"
    )
    path = _write_text(package_dir, "modules/UIBuilder.lua", code)
    return BuilderResult(
        "ui.group.v1",
        "ui",
        "BUILT",
        "UI module generated.",
        [
            _artifact(
                package_dir,
                "luau_module",
                "UIBuilder",
                path,
                elements=elements,
            )
        ],
    )


def _timeline_builder(
    command: dict[str, Any],
    blueprint: dict[str, Any],
    package_dir: Path,
) -> BuilderResult:
    actions = blueprint.get("action_timeline") or []
    code = (
        "local M={}\n"
        f"local ACTIONS={_lua(actions)}\n"
        "function M.Run(c)\n"
        "    table.sort(ACTIONS,function(a,b) return (a.start or 0)<(b.start or 0) end)\n"
        "    for _,a in ipairs(ACTIONS) do\n"
        "        task.spawn(function()\n"
        "            task.wait(tonumber(a.start) or 0)\n"
        "            local m=c.mechanics['Mechanic_'..tostring(a.action)]\n"
        "            if m and m.Run then\n"
        "                m.Run({humanoid=c.humanoid,root=c.root,duration=math.max(.25,(tonumber(a['end']) or 1)-(tonumber(a.start) or 0))},a.properties or {})\n"
        "            end\n"
        "        end)\n"
        "    end\n"
        "end\n"
        "return M\n"
    )
    path = _write_text(
        package_dir,
        "modules/TimelineBuilder.lua",
        code,
    )
    return BuilderResult(
        "timeline.master.v1",
        "timeline",
        "BUILT",
        "Timeline module generated.",
        [
            _artifact(
                package_dir,
                "luau_module",
                "TimelineBuilder",
                path,
                action_count=len(actions),
            )
        ],
    )


def _bootstrap_builder(
    command: dict[str, Any],
    blueprint: dict[str, Any],
    package_dir: Path,
) -> BuilderResult:
    code = (
        "local RS=game:GetService('ReplicatedStorage')\n"
        "local Players=game:GetService('Players')\n"
        "local modules=RS:WaitForChild('AIVideoGenPackage'):WaitForChild('Modules')\n"
        "local Character=require(modules:WaitForChild('CharacterBuilder'))\n"
        "local Camera=require(modules:WaitForChild('CameraBuilder'))\n"
        "local UI=require(modules:WaitForChild('UIBuilder'))\n"
        "local Timeline=require(modules:WaitForChild('TimelineBuilder'))\n"
        "local mechanics={}\n"
        "for _,m in ipairs(modules:WaitForChild('Mechanics'):GetChildren()) do\n"
        "    if m:IsA('ModuleScript') then mechanics[m.Name]=require(m) end\n"
        "end\n"
        "local player=Players.LocalPlayer\n"
        "local character=player.Character or player.CharacterAdded:Wait()\n"
        "local humanoid=Character.Configure(character)\n"
        "local context={character=character,humanoid=humanoid,root=character:WaitForChild('HumanoidRootPart'),mechanics=mechanics}\n"
        "UI.Build(context); Camera.Start(context); Timeline.Run(context)\n"
        "print('[AIVideoGen] Generated scene started.')\n"
    )
    path = _write_text(
        package_dir,
        "scripts/GeneratedScene.client.lua",
        code,
    )
    return BuilderResult(
        "bootstrap.client.v1",
        "bootstrap",
        "BUILT",
        "Client bootstrap generated.",
        [_artifact(package_dir, "client_script", "GeneratedScene", path)],
    )


BuilderFunction = Callable[
    [dict[str, Any], dict[str, Any], Path],
    BuilderResult,
]


def _resolve_builder(builder_id: str) -> BuilderFunction | None:
    if builder_id.startswith("scene."):
        return _environment_builder
    if builder_id.startswith("character."):
        return _character_builder
    if builder_id.startswith("mechanic."):
        return _mechanic_builder
    if builder_id.startswith("camera."):
        return _camera_builder
    if builder_id.startswith("ui."):
        return _ui_builder
    if builder_id == "timeline.master.v1":
        return _timeline_builder
    if builder_id == "bootstrap.client.v1":
        return _bootstrap_builder
    return None


def _blueprint_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, dict):
        return value
    raise TypeError("Unsupported Roblox Brain plan.")


def _requested_builders(
    blueprint: dict[str, Any],
) -> list[str]:
    requested = [
        str(item.get("builder_id") or "")
        for item in blueprint.get("execution_plan") or []
        if item.get("builder_id")
    ]
    required = [
        "scene.environment_graph.v1",
        "character.spawn_r15.v1",
        "camera.controller.v1",
        "ui.group.v1",
        "timeline.master.v1",
        "bootstrap.client.v1",
    ]
    requested.extend(required)
    return list(dict.fromkeys(requested))


def _command_for(
    builder_id: str,
    blueprint: dict[str, Any],
) -> dict[str, Any]:
    for item in blueprint.get("execution_plan") or []:
        if str(item.get("builder_id") or "") == builder_id:
            result = dict(item)
            result["builder_id"] = builder_id
            return result

    if builder_id == "scene.environment_graph.v1":
        return {
            "builder_id": builder_id,
            "command": "build_environment",
            "properties": blueprint.get("environment_graph") or {},
        }
    if builder_id == "character.spawn_r15.v1":
        return {
            "builder_id": builder_id,
            "command": "spawn_character",
            "properties": blueprint.get("character_state") or {},
        }

    return {
        "builder_id": builder_id,
        "command": builder_id,
        "properties": {},
    }


def build_scene_package(source_name: str) -> BuildManifest:
    brain_plan = (
        load_roblox_brain_plan(source_name)
        or build_roblox_brain_plan(source_name)
    )
    blueprint = _blueprint_dict(brain_plan)

    build_id = (
        f"{int(time.time())}_{_safe_name(Path(source_name).stem)}_"
        f"{uuid.uuid4().hex[:8]}"
    )
    package_dir = OUTPUT_DIR / build_id
    package_dir.mkdir(parents=True, exist_ok=True)

    _write_json(
        package_dir,
        "blueprint/roblox_brain.json",
        blueprint,
    )

    results: list[BuilderResult] = []
    artifacts: list[Artifact] = []
    missing: list[str] = []
    warnings: list[str] = []

    for builder_id in _requested_builders(blueprint):
        builder = _resolve_builder(builder_id)
        if builder is None:
            missing.append(builder_id)
            warnings.append(
                f"No Part 3A builder registered for {builder_id}."
            )
            continue

        try:
            result = builder(
                _command_for(builder_id, blueprint),
                blueprint,
                package_dir,
            )
        except Exception as exc:
            result = BuilderResult(
                builder_id=builder_id,
                phase=builder_id.split(".", 1)[0],
                status="FAILED",
                message=str(exc),
            )

        results.append(result)
        artifacts.extend(result.artifacts)
        warnings.extend(result.warnings)

    handoff = _write_json(
        package_dir,
        "studio_handoff/plugin_package.json",
        {
            "source_name": source_name,
            "build_id": build_id,
            "blueprint": blueprint,
            "artifacts": [asdict(item) for item in artifacts],
            "missing_builders": missing,
            "warnings": warnings,
        },
    )
    artifacts.append(
        _artifact(
            package_dir,
            "studio_handoff",
            "plugin_package",
            handoff,
        )
    )

    status = (
        "FAILED"
        if any(result.status == "FAILED" for result in results)
        else "BUILT_WITH_WARNINGS"
        if warnings or missing
        else "BUILT"
    )

    manifest = BuildManifest(
        source_name=source_name,
        build_id=build_id,
        status=status,
        package_dir=str(package_dir.relative_to(BASE)).replace("\\", "/"),
        results=results,
        artifacts=artifacts,
        missing_builders=missing,
        warnings=warnings,
        created_at=time.time(),
    )
    manifest.save()
    return manifest


def list_scene_builds(limit: int = 100) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not OUTPUT_DIR.exists():
        return rows

    for path in OUTPUT_DIR.glob("*/build_manifest.json"):
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
