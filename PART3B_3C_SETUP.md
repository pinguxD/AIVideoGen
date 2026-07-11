# Roblox Place Generator — Parts 3B + 3C

This replaces the Studio plugin workflow.

## Part 3B

Generates a complete local Roblox XML place file:

```text
outputs/generated_places/<reference>_<build_id>.rbxlx
```

The place contains:

```text
Workspace
└── AIVideoGenGenerated
    ├── generated environment parts
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

StarterPlayer
└── StarterPlayerScripts
    └── GeneratedScene
```

## Part 3C

Launches Roblox Studio with the generated `.rbxlx` place.

Roblox Studio officially supports opening a local `.rbxl` or `.rbxlx` file by
using `--task EditFile` and `--localPlaceFile`.

## Install

Copy into `radar/`:

```text
roblox_place_generator.py
roblox_place_web.py
```

Add to `NAV_ITEMS`:

```python
("/roblox-place-generator", "Roblox Place Generator"),
```

Register above `if __name__ == "__main__":`

```python
from radar.roblox_place_web import register_roblox_place_routes

register_roblox_place_routes(
    app,
    page,
    esc,
)
```

Restart:

```powershell
Ctrl + C
py app.py
```

Open:

```text
http://127.0.0.1:5000/roblox-place-generator
```

Click:

```text
Generate Place & Open Studio
```

## Optional Studio path override

The launcher normally detects the newest Roblox Studio installation under:

```text
%LOCALAPPDATA%\Roblox\Versions\
```

Override it in `.env` when needed:

```text
ROBLOX_STUDIO_PATH=C:\Users\YOUR_NAME\AppData\Local\Roblox\Versions\version-...\RobloxStudioBeta.exe
```

## Important first test

The generator creates a standards-based XML `.rbxlx` place and validates that
the XML is well-formed before saving. Roblox Studio is still the final parser
and validator of Roblox-specific properties.

After Studio opens, check Explorer for:

```text
Workspace/AIVideoGenGenerated
ReplicatedStorage/AIVideoGenPackage
StarterPlayer/StarterPlayerScripts/GeneratedScene
```

Then press Play.


## Validation and project folders

Every generated game now also creates:

```text
outputs/generated_projects/<reference>_<build_id>/
├── GeneratedGame.rbxlx
├── blueprint.json
├── metadata.json
├── modules/
├── scripts/
├── assets/
├── sounds/
└── thumbnails/
```

Before Studio is opened, the program checks:

- well-formed XML;
- Workspace;
- ReplicatedStorage;
- StarterPlayer;
- GeneratedScene;
- AIVideoGenPackage/Modules;
- Roblox's documented 100 MB place-size limit.

The launcher tries, in order:

1. Windows file association via `os.startfile(GeneratedGame.rbxlx)`;
2. the official positional Studio form: `RobloxStudioBeta.exe GeneratedGame.rbxlx`;
3. the official explicit `--task EditFile --localPlaceFile` form.

Use the **Validate** button on the generated-places table to inspect all checks.
