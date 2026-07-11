# Recreation Audio Engine v1

This package adds automatic TTS and sound-effect resolution after the Roblox
Recreation Lab stage.

## Files

Copy into `radar/`:

```text
tts_engine.py
sfx_resolver.py
audio_production_engine.py
audio_production_web.py
```

## Environment values

Add to `.env`:

```text
ELEVENLABS_API_KEY=your_key
ELEVENLABS_VOICE_ID=your_voice_id
ELEVENLABS_MODEL_ID=eleven_multilingual_v2
```

The Freesound key already used by your existing Sound Library remains:

```text
FREESOUND_API_KEY=your_key
```

## app.py

Add to `NAV_ITEMS`:

```python
("/audio-production", "AI Audio Production"),
```

Add above `if __name__ == "__main__":`

```python
from radar.audio_production_web import register_audio_production_routes

register_audio_production_routes(
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
http://127.0.0.1:5000/audio-production
```

## Workflow

1. Analyze the reference in Full Video Analysis.
2. Run Roblox Recreation Lab.
3. Open AI Audio Production.
4. Enter the original narration script.
5. Generate TTS and resolve effects.

Outputs:

```text
outputs/generated_voiceovers/
outputs/resolved_sound_effects/
outputs/audio_production/
```

The resolver maps detected sound families to multiple Freesound searches, avoids
high-risk/blocked assets, prevents duplicate sound files within one video, and
stores creator/license attribution.

This version generates TTS from a supplied original script. Automatic script
writing is intentionally left for the later Script Writer stage.
