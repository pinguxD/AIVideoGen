# Trend Radar X Creator AI+

This version adds two new automation modules:

## 1) Sound Finder
Trend Radar now detects which sound types your auto-create projects need and creates:

- `outputs/sound_finder.csv`
- website page: `outputs/site/sounds.html`

It gives search links for sound sources such as Pixabay, Freesound, and MyInstants, plus copyright-risk notes.

**Important:** Do not blindly reuse copyrighted audio. Prefer CC0/free-to-use sounds, sounds you create yourself, or sounds you are allowed to use.

You can manually download a direct audio file URL you are allowed to use:

```powershell
py download_sound.py DIRECT_AUDIO_URL optional_filename.mp3
```

Downloaded sounds go to:

```text
assets/sounds/
```

## 2) Raw Gameplay Clip Miner
Put full gameplay recordings here:

```text
assets/raw_gameplay/
```

Then run:

```powershell
py mine_gameplay.py
```

It will scan the long recordings for motion/visual-change moments and cut reusable clips into:

```text
assets/source/mined/
```

Report:

```text
outputs/clip_miner_report.csv
```

You can also let Trend Radar run the miner automatically by setting this in `.env`:

```env
MINE_RAW_GAMEPLAY=true
MAX_MINED_CLIPS_PER_FILE=8
MINED_CLIP_LENGTH_SECONDS=9
```

## Normal Run

```powershell
py -m pip install -r requirements.txt
py trend_radar.py
```

Open:

```text
outputs/site/index.html
```

Useful pages:

- Auto Studio: `outputs/site/auto_studio.html`
- Assets: `outputs/site/assets.html`
- Sound Finder: `outputs/site/sounds.html`
- Viral Library: `outputs/site/library.html`

## Asset folders

```text
assets/source/       # reusable clips/images
assets/source/mined/ # AI-mined clips from raw gameplay
assets/sounds/       # reusable meme/sfx audio
assets/raw_gameplay/ # full gameplay recordings
```

## Safe workflow

Trend Radar does **not** automatically steal YouTube clips. It finds formats and tells you whether it can create them from your asset library. If assets are missing, it tells you what to provide.
