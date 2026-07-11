# Roblox Studio Execution Bridge - Stage 1

Copy into `radar/`:

```text
roblox_studio_bridge.py
roblox_generation_web.py
```

Add to `NAV_ITEMS` in `app.py`:

```python
("/roblox-generation", "Roblox Studio Generation"),
```

Add above `if __name__ == "__main__":`

```python
from radar.roblox_generation_web import register_roblox_generation_routes
register_roblox_generation_routes(app, page, esc)
```

Optional `.env` overrides:

```text
ROBLOX_STUDIO_PATH=C:\Users\YOUR_NAME\AppData\Local\Roblox\Versions\version-...\RobloxStudioBeta.exe
ROBLOX_TEMPLATE_PLACE=C:\Path\To\AIVideoGenTemplate.rbxl
```

When no template is configured, Studio opens its default baseplate.

Restart:

```powershell
Ctrl + C
py app.py
```

Open:

```text
http://127.0.0.1:5000/roblox-generation
```

Click `Start Roblox generation - Stage 1`.

The importer inserts:

```text
StarterPlayer
└── StarterPlayerScripts
    └── GeneratedScene
```

It also stores the scene spec in ReplicatedStorage.

Stage 1 launches and imports only. You still press Play manually.
