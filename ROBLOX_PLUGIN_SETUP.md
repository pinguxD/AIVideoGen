# Roblox Studio Plugin Bridge v1

This replaces the unreliable command-line source injection with a persistent
Studio plugin.

The plugin uses official Studio plugin APIs, `HttpService`, and
`ScriptEditorService:UpdateSourceAsync()`.

## 1. Copy Python files

Copy into `radar/`:

```text
roblox_plugin_bridge.py
roblox_plugin_web.py
```

## 2. Register Flask routes

Add to `NAV_ITEMS`:

```python
("/roblox-plugin", "Roblox Studio Plugin Bridge"),
```

Add above `if __name__ == "__main__":`

```python
from radar.roblox_plugin_web import register_roblox_plugin_routes

register_roblox_plugin_routes(
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
http://127.0.0.1:5000/roblox-plugin
```

## 3. Install the Studio plugin

Open Roblox Studio.

Create a new Script in a blank place, paste the contents of:

```text
roblox_plugin/AIVideoGenPlugin.lua
```

Then use Studio's plugin creation flow to save/publish it as a local plugin.
Depending on your Studio version this is usually available from the Plugins tab
or from the script's context menu as **Save as Local Plugin**.

After installation, restart Studio.

You should see an **AIVideoGen** toolbar with a **Fetch & Build** button.

## 4. Allow localhost HTTP

Keep the Flask app running.

The first time the plugin contacts:

```text
http://127.0.0.1:5000
```

Studio may ask for permission. Approve only this local address.

Roblox documents that plugins can use `HttpService`, and users can approve or
revoke the plugin's access to a particular web address through Plugin
Management.

## 5. Use it

1. Run Recreation Lab for a reference.
2. Open `/roblox-plugin`.
3. Click **Queue scene for Studio plugin**.
4. Open Studio.
5. Click **AIVideoGen → Fetch & Build**.
6. Verify:
   - `Workspace/AIVideoGenGenerated`
   - `StarterPlayer/StarterPlayerScripts/GeneratedScene`
   - `StarterGui/AIVideoGenGui` when the spec contains GUI
   - `ReplicatedStorage/AIVideoGen_<job id>`
7. Press Play.

## What v1 builds

- a procedural environment from the scene template;
- basic obby, hospital, or platform layouts;
- generated GUI sliders;
- the scene-spec manifest;
- the generated LocalScript using `UpdateSourceAsync`;
- import metadata and job completion reporting.

This is the correct foundation for Stage 2, where the plugin will construct
avatars, camera rigs, animations, mechanics, lighting, and automatically enter
Play mode.
