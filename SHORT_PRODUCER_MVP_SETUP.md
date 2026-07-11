# Short Producer MVP

This is the fastest practical path to the first Creator AI-generated Short.

Pipeline:

```text
GeneratedGame.rbxlx
→ open Roblox Studio
→ press F5 automatically
→ record the Roblox Studio window with FFmpeg
→ center-crop to 9:16
→ scale to 1080×1920
→ optionally mix an existing generated audio track
→ export MP4
```

Run:

```powershell
py app.py
```

Open:

```text
http://127.0.0.1:5000/short-producer
```

FFmpeg must be installed. Verify:

```powershell
ffmpeg -version
```

Or set:

```text
FFMPEG_PATH=C:\ffmpeg\bin\ffmpeg.exe
```

Recommended first test:

```text
Duration: 15
Studio launch wait: 12
Play-mode wait: 2
Window title: Roblox Studio
Audio: No audio yet
```

Output:

```text
outputs/short_producer/<job_id>/
├── studio_capture.mp4
└── final_short_1080x1920.mp4
```

This first milestone deliberately targets a valid vertical gameplay MP4.
The next milestone adds automatic TTS selection, captions, SFX timing, music,
and final retention editing.
