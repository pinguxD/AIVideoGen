# Roblox Recreation Intelligence v1

Copy all included files into the matching project locations.

Add to `NAV_ITEMS` in `app.py`:

```python
("/recreation-lab", "Roblox Recreation Lab"),
```

Add this above `if __name__ == "__main__":`

```python
from radar.recreation_web import register_recreation_routes
register_recreation_routes(app, page, esc)
```

Restart with:

```powershell
Ctrl + C
py app.py
```

Open:

```text
http://127.0.0.1:5000/recreation-lab
```

This milestone:
- analyzes the full reference;
- detects hard cuts, flashes, blur transitions, whip pans, zoom transitions and fades;
- detects caption and meme/image-insert ranges;
- classifies isolated sound-effect families;
- scores environment, avatar, camera, mechanic, UI, editing, sound and voice feasibility;
- decides SELF_GENERATE, SELF_GENERATE_WITH_ASSETS, NEEDS_USER_INPUT or CANNOT_RECREATE_RELIABLY;
- writes a Roblox scene specification;
- generates a starter Roblox Studio R15 LocalScript.

Generated folders:

```text
outputs/recreation_intelligence/
outputs/roblox_scene_specs/
outputs/roblox_studio_projects/
```

This is an advanced foundation, not yet a perfect pixel-to-Roblox reverse engineer.
Exact game/map recognition, OCR, speech transcription, frame embeddings, object
detection and arbitrary Roblox mechanic inference are the next model layer.
