# Audio Intelligence Autopilot v2

This upgrade removes the old manual warnings:

```text
identify or approve unknown sound effects
voice or TTS choice
```

It now:

- analyzes the reference voice;
- estimates pacing, energy, delivery and pitch band;
- searches the user's ElevenLabs voices;
- automatically chooses the closest available voice;
- configures TTS style/stability from the reference;
- generates the voice-over;
- generates every detected sound effect with ElevenLabs Sound Effects;
- stores a complete audio-autopilot manifest.

## Copy files

Copy these files into `radar/`:

```text
voice_profiler.py
elevenlabs_audio_client.py
audio_autopilot.py
audio_autopilot_web.py
```

## Environment

Add to `.env`:

```text
ELEVENLABS_API_KEY=your_key
```

An optional fallback:

```text
ELEVENLABS_VOICE_ID=your_fallback_voice_id
```

## app.py

Add to `NAV_ITEMS`:

```python
("/audio-autopilot", "Audio Intelligence Autopilot"),
```

Add above the `if __name__ == "__main__":` block:

```python
from radar.audio_autopilot_web import register_audio_autopilot_routes

register_audio_autopilot_routes(
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
http://127.0.0.1:5000/audio-autopilot
```

## Workflow

1. Analyze the reference.
2. Run Recreation Lab.
3. Open Audio Intelligence Autopilot.
4. Paste the original narration script.
5. Click `Run full audio autopilot`.

Outputs:

```text
outputs/generated_voiceovers/
outputs/generated_sound_effects/
outputs/audio_autopilot/
```

Automatic script writing is the next stage. For now, the system uses an original
script supplied by the user and generates all audio without requiring manual
voice or sound-effect selection.
