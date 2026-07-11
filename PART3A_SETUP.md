# Roblox Scene Builder — Part 3A

Copy into `radar/`:

```text
scene_builder_engine.py
scene_builder_web.py
```

Add to `NAV_ITEMS`:

```python
("/scene-builder", "Roblox Scene Builder"),
```

Register above `if __name__ == "__main__":`

```python
from radar.scene_builder_web import register_scene_builder_routes

register_scene_builder_routes(
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
http://127.0.0.1:5000/scene-builder
```

Part 3A currently generates:

- environment module;
- R15 character module;
- walk, jump, grow, shrink, turn, and idle modules;
- camera controller;
- UI module;
- master timeline;
- client bootstrap;
- Studio handoff JSON;
- build manifest.

Outputs:

```text
outputs/scene_builder/<build_id>/
├── blueprint/
├── modules/
├── scripts/
├── studio_handoff/
└── build_manifest.json
```

Unknown mechanic builders become visible stubs. Unknown non-mechanic builders
are listed as missing instead of silently disappearing.

Part 3B will make the Studio plugin install these generated files as actual
ModuleScripts and LocalScripts and assemble the playable hierarchy.
