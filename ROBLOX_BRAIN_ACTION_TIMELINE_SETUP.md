# Roblox Brain Part 2 — Multi-Action Timeline Upgrade

Replace:

```text
radar/roblox_brain.py
radar/roblox_brain_web.py
```

Also copy the included plugin bridge files over the current versions. They remain
compatible and attach the richer Brain plan to every Studio job.

Restart:

```powershell
Ctrl + C
py app.py
```

Open `/roblox-brain` and click **Rebuild full Roblox Brain plan**.

The new plan contains:

```text
core_mechanic
supporting_actions
action_timeline
camera_timeline
editing_timeline
audio_timeline
multiple UI elements
builder_sequence
```

Old Part 2 JSON files are automatically ignored and rebuilt.

Important: action timing is currently a structured heuristic using detected scene
boundaries and visual motion. It is the correct interface for Part 3, but exact
walk/jump/turn timing will become more accurate when pose/action recognition is
added later.
