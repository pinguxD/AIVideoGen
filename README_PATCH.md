# Video Intelligence v1 patch

Built for the current `pinguxD/AIVideoGen` main branch.

## What it adds

- Multi-label format classification instead of one keyword-only label
- Confidence score and explicit `manual_review` state
- Evidence shown for every classification
- Metadata signals from title, description, tags, duration and thumbnail statistics
- Stronger disambiguation between Guess Voice, sound replacement, animation/skit, facts, tutorials, stories, challenges and memes
- Manual correction page at `http://127.0.0.1:5000/classification-review`
- Persistent corrections in `outputs/video_classification.db`
- User corrections override future scans
- Low-confidence videos are blocked from automatic Creator AI generation
- Opportunity score is discounted when classification confidence is weak

## Install

Extract this patch, open a terminal in your AIVideoGen project root, then run:

```powershell
py "C:\path\to\video_intelligence_patch\apply_video_intelligence_patch.py"
```

Then rerun the scanner:

```powershell
py trend_radar.py
```

Restart the website:

```powershell
py app.py
```

Open:

```text
http://127.0.0.1:5000/classification-review
```

## Important limitation

This version makes metadata classification much more careful and learnable, but it still does not download and fully watch each YouTube Short. Thumbnail analysis currently measures visual properties, not exact on-screen text or character identity. Real frame/audio understanding is the next stage and should be added only after this review dataset gives us a measurable benchmark.
