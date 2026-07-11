from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from .full_video_analyzer import BASE

OUT = BASE / "outputs" / "roblox_studio_projects"

def generate_lua(spec: dict[str, Any]):
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in Path(str(spec.get("source_file") or "reference")).stem).strip("_") or "reference"
    folder = OUT / safe
    folder.mkdir(parents=True, exist_ok=True)
    avatar = (spec.get("avatars") or [{}])[0]
    scale = avatar.get("scale") or {}
    position = (spec.get("camera") or {}).get("position") or [0, 5, -10]
    values = {
        "height": float(scale.get("height", 1)),
        "width": float(scale.get("width", 1)),
        "head": float(scale.get("head", 1)),
        "body": float(scale.get("body_type", 0)),
        "x": float(position[0]), "y": float(position[1]), "z": float(position[2]),
        "duration": float(spec.get("duration") or 8),
    }
    lua = '''-- Trend Radar X generated Roblox scene v1
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local player = Players.LocalPlayer
local character = player.Character or player.CharacterAdded:Wait()
local humanoid = character:WaitForChild("Humanoid")
local root = character:WaitForChild("HumanoidRootPart")
local camera = workspace.CurrentCamera
camera.CameraType = Enum.CameraType.Scriptable

local function setScale(name, value)
    local item = humanoid:FindFirstChild(name)
    if item and item:IsA("NumberValue") then item.Value = value end
end

setScale("BodyHeightScale", {height})
setScale("BodyWidthScale", {width})
setScale("HeadScale", {head})
setScale("BodyTypeScale", {body})

local ground = Instance.new("Part")
ground.Name = "GeneratedGround"
ground.Size = Vector3.new(40, 1, 40)
ground.Position = Vector3.new(0, 0, 0)
ground.Anchored = true
ground.Parent = workspace

local offset = Vector3.new({x}, {y}, {z})
local started = os.clock()
local duration = {duration}
RunService.RenderStepped:Connect(function()
    local elapsed = os.clock() - started
    if elapsed > duration then return end
    local push = math.clamp(elapsed / math.max(duration, 0.1), 0, 1) * 2
    camera.CFrame = CFrame.lookAt(
        root.Position + offset + Vector3.new(0, 0, push),
        root.Position + Vector3.new(0, 2, 0)
    )
end)
'''.format(**values)
    lua_path = folder / "GeneratedScene.client.lua"
    lua_path.write_text(lua, encoding="utf-8")
    manifest = folder / "scene_spec.json"
    manifest.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    return lua_path, manifest
