# Trend Radar X — Creator Engine

This upgrade adds a working first-generation automatic Shorts pipeline.

## What it does

1. Reads `outputs/final_opportunities.csv` (or `trend_report.csv`).
2. Converts supported viral formats into Creator AI projects.
3. Searches your mined gameplay in `assets/source/mined/`.
4. Prefers clips you rated highly in `outputs/clip_miner_report.csv`.
5. Checks your local sound library.
6. Optionally searches/downloads Creative Commons sound previews from Freesound.
7. Produces real 1080×1920 MP4 drafts for:
   - Guess the Voice
   - sound replacement / funny scream
   - simple fact-card backgrounds (requires fact text review)
8. Stores sound source, creator, licence and attribution data.

## Install

Keep your existing `.env`, `assets/`, and `outputs/` folders. Overwrite the code files, then:

```powershell
py -m pip install -r requirements.txt
```

MoviePy 1.x is required by this project.

## Optional automatic sound downloads

Create a Freesound API key and add it to `.env`:

```env
FREESOUND_API_KEY=your_key_here
```

The program skips clearly non-commercial licences and records attribution in:

```text
assets/sounds/sound_index.csv
outputs/drafts/<video_id>_sound_credits.txt
```

Always review the licence/risk column before publishing a monetized video.

## Website workflow

Start the website:

```powershell
py app.py
```

Open:

```text
http://127.0.0.1:5000/creator-ai
```

Then:

- **Analyze viral candidates**: uses existing local sounds only.
- **Analyze + find sounds**: searches Freesound for missing sound types.
- **Generate draft**: renders an MP4 when the project is `AUTO_READY`.

Sound library:

```text
http://127.0.0.1:5000/sound-library
```

## Command-line workflow

```powershell
py creator_ai.py analyze --fetch-sounds --limit 100
py creator_ai.py generate VIDEO_ID
```

Drafts are written to:

```text
outputs/drafts/
```

## Important limitations

- It does not download or reuse other creators' YouTube footage.
- It uses your own mined gameplay and licensed sound assets.
- Format detection is currently metadata/rule based; it does not yet visually understand the inspiration video.
- Generated drafts are a starting point and should be reviewed before upload.
