# Full-Video Map Blueprint

This adds the missing intermediate map stage.

## New pipeline

```text
Full reference video
→ 60–140 samples across the whole timeline
→ fixed overlay masking
→ conservative avatar masking
→ platform / walkway / red-pad detection
→ cross-frame tracking
→ repeated-view merging
→ shared backdrop classification
→ depth ordering
→ MapBlueprint.json
→ top-down preview
→ review / edit / approve
→ constrained World Planner
→ Roblox compiler
```

## Critical behavior changes

- Roblox generation is blocked until the Map Blueprint is approved.
- Open maps cannot generate ceilings.
- Open maps can have at most one shared backdrop wall.
- The builder is forbidden from creating one room shell per platform.
- The World Planner consumes the approved blueprint instead of guessing topology again.

## Use

Run:

```powershell
py app.py
```

Open:

```text
http://127.0.0.1:5000/map-blueprint
```

Then:

1. Click **Watch Full Video & Build Blueprint**.
2. Review the top-down map and the full-video contact sheet.
3. Edit structure types, positions or sizes when needed.
4. Click **Approve Map**.
5. Click **Generate Roblox Place**.

Outputs:

```text
outputs/map_blueprints/<reference>/MapBlueprint.json
outputs/map_blueprints/<reference>/map_preview.png
outputs/map_blueprints/<reference>/full_video_contact_sheet.jpg
```

The target reference should now be represented as an open-sky route with one
shared backdrop, route platforms, a trigger pad and a final reveal platform,
rather than repeated enclosed room cells.
