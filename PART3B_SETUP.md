# Roblox Scene Builder — Part 3B

Part 3B installs a Part 3A package into the currently open Roblox Studio place.

## Python files

Copy into `radar/`:

```text
scene_builder_plugin_bridge.py
scene_builder_plugin_web.py
```

## Register the page

Add to `NAV_ITEMS`:

```python
("/scene-builder-plugin", "Roblox Studio Installer"),
```

Add above `if __name__ == "__main__":`

```python
from radar.scene_builder_plugin_web import (
    register_scene_builder_plugin_routes,
)

register_scene_builder_plugin_routes(
    app,
    page,
    esc,
)
```

Restart Flask:

```powershell
Ctrl + C
py app.py
```

Open:

```text
http://127.0.0.1:5000/scene-builder-plugin
```

Queue a successful Part 3A package.

## Roblox Studio plugin

Replace the old local plugin source with:

```text
roblox_plugin/AIVideoGenPart3B.lua
```

Save it as a local plugin and restart Studio.

The toolbar will contain:

```text
AIVideoGen → Fetch & Install
```

Keep Flask running, then click that button.

## What Part 3B installs

```text
Workspace
└── AIVideoGenGenerated
    ├── generated level parts
    └── GeneratedSpawn

ReplicatedStorage
└── AIVideoGenPackage
    ├── BlueprintJSON
    └── Modules
        ├── EnvironmentBuilder
        ├── CharacterBuilder
        ├── CameraBuilder
        ├── UIBuilder
        ├── TimelineBuilder
        └── Mechanics
            ├── Mechanic_walk
            ├── Mechanic_grow
            └── ...

StarterPlayer
└── StarterPlayerScripts
    └── GeneratedScene

ServerScriptService
└── AIVideoGenBuildInfo
```

It also applies the selected lighting preset.

Press **Play** after installation to test the generated scene.

## Current boundary

Part 3B:
- transfers the package from Python to Studio;
- creates the Studio hierarchy;
- creates ModuleScripts and a LocalScript;
- writes generated Luau source through ScriptEditorService;
- creates the visible environment in edit mode;
- applies lighting;
- reports completion or failure to Flask.

Part 3C will automatically run a test, capture output/runtime errors, validate the
scene, and request repairs from Python.
