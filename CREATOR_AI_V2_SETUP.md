# Creator AI v2

Creator AI v2 replaces the older plugin/installer workflow with one clean
generation pipeline.

## Copy into `radar/`

```text
creator_ai_v2.py
creator_ai_v2_web.py
roblox_template_compiler.py
```

## Register the page

Add to `NAV_ITEMS`:

```python
("/creator-ai-v2", "Creator AI v2"),
```

Add above `if __name__ == "__main__":`

```python
from radar.creator_ai_v2_web import register_creator_ai_v2_routes

register_creator_ai_v2_routes(
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
http://127.0.0.1:5000/creator-ai-v2
```

## One-time template setup

Roblox does not publish a complete standalone XML schema for authoring every
place detail safely from scratch. Creator AI v2 therefore modifies a known-valid
Studio place rather than inventing the entire file.

Do this once:

1. Open Roblox Studio.
2. Create a blank Baseplate.
3. Choose **File → Save to File**.
4. Save it as an `.rbxlx` file.
5. Upload that file on the Creator AI v2 page.

It is stored as:

```text
assets/roblox_templates/AIVideoGenBase.rbxlx
```

After this one-time setup, generation is one button.

## One-button pipeline

```text
Video Blueprint
→ Roblox Brain
→ Part 3A Builder Engine
→ Template-based Place Compiler
→ Local Validation
→ GeneratedGame.rbxlx
→ Open Studio
```

Generated projects are written to:

```text
outputs/creator_ai_v2/<reference>_<project_id>/
├── GeneratedGame.rbxlx
├── blueprint.json
├── metadata.json
├── validation.json
├── scene_package/
├── assets/
├── sounds/
└── thumbnails/
```

No Roblox Studio plugin is used.
