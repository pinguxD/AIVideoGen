# Part 3B Auto-Open Upgrade

Copy these into `radar/`:

- `scene_builder_plugin_bridge.py`
- `scene_builder_plugin_web.py`
- `scene_builder_plugin_launcher.py`
- `AIVideoGenPart3B.lua`

Keep your existing app.py registration unchanged.

Restart Flask and open `/scene-builder-plugin`.

New buttons:

- Generate & Open Plugin File
- Open Generated Plugin Folder
- Queue + Open Plugin + Launch Studio
- Queue only

The generated plugin is written to:

`outputs/roblox_plugin/AIVideoGenPart3B.lua`

Roblox requires one manual `Save as Local Plugin` confirmation. After that first install, future packages can be queued and fetched without reopening or reinstalling the plugin.
