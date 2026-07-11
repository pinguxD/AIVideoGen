# Viral Gaming Story Scout — v1

This is the first stage of the Story Writing AI.

## Workflow

```text
YouTube Data API
→ search current storytelling Shorts with gaming backgrounds
→ enrich with views, likes, comments, duration and channel size
→ rank viral velocity, engagement, breakout strength, story signals and gaming signals
→ human review
→ approve or reject
→ manually download approved reference
→ upload local file into the program
→ mark ready for Story Analysis
```

## Run

```powershell
py app.py
```

Open:

```text
http://127.0.0.1:5000/story-scout
```

## Required `.env`

```text
YOUTUBE_API_KEY=your_key_here
```

## Default searches

```text
storytime minecraft parkour shorts
reddit story gameplay shorts
storytime subway surfers shorts
gaming background story shorts
minecraft story shorts
roblox storytime shorts
```

The scan uses only a selected number of queries per run because YouTube
`search.list` is quota-expensive.

## Human approval

The program does not automatically treat views as proof of quality. You open
each candidate and approve or reject it.

Approved videos are not downloaded automatically. Download the reference using
your own lawful workflow, then upload the local video through the approved
candidate card.

Imported references are stored here:

```text
assets/story_references/pending/<youtube_video_id>/
├── reference.mp4
└── metadata.json
```

The metadata includes the discovery-time views, velocity, engagement,
storytelling score, gaming-background score and your notes.

## Next milestone

The next module will analyze imported references for:

- transcript and speech speed;
- hook wording pattern;
- sentence lengths;
- story beats;
- curiosity gaps;
- escalation;
- twist placement;
- payoff and loop;
- caption density;
- scene changes;
- background-gameplay intensity.

It will learn reusable structural patterns, not copy exact scripts.
