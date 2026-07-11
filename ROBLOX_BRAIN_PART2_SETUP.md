# Roblox Brain - Part 2

Part 2 converts the recreation analysis into reusable Roblox concepts.

## Files

Copy into `radar/`:

```text
roblox_brain.py
roblox_brain_web.py
```

Replace the current plugin bridge files with:

```text
roblox_plugin_bridge.py
roblox_plugin_web.py
```

The replacement plugin bridge attaches the Roblox Brain plan to every Studio job.

## app.py

Add to `NAV_ITEMS`:

```python
("/roblox-brain", "Roblox Brain"),
```

Add above `if __name__ == "__main__":`

```python
from radar.roblox_brain_web import register_roblox_brain_routes

register_roblox_brain_routes(
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
http://127.0.0.1:5000/roblox-brain
```

## Part 2 vocabulary

Scenes:
- simple platform
- simple obby
- hospital
- city
- horror corridor
- character showcase

Mechanics:
- grow
- shrink
- walk
- chase
- press button
- spawn object
- reveal object
- custom game-specific mechanic

Cameras:
- static
- third-person follow
- rear close-up
- orbit
- push-in

UI:
- size slider
- counter
- warning label
- arrow
- circle highlight

## Important behavior

- Narrated format alone never chooses Animal Hospital.
- Scene choice depends on scene/mechanic context.
- Avatar-size references choose character showcase + grow.
- Every result contains a `builder_sequence`.
- Part 3 will execute this sequence in Studio.

Output:

```text
outputs/roblox_brain/<reference>.roblox_brain.json
```
