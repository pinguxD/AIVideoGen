# Video Intelligence direct source files

This package contains direct replacement source files — no installer.

Copy these into your project:

- `radar/scanner.py`
- `radar/scoring.py`
- `radar/classification_feedback.py`
- `radar/classification_web.py`

Keep your existing:

- `radar/video_intelligence.py`
- `assets/`
- `outputs/`
- `.env`

Then follow `APP_INTEGRATION.md` for the two small `app.py` edits.

## What changes

- YouTube tags are saved.
- Scanner calls `enrich_video()`.
- Old keyword scoring respects Video Intelligence output.
- Low-confidence classifications remain in `trend_report.csv`.
- Low-confidence classifications are excluded from `final_opportunities.csv`.
- Creator AI therefore only receives accepted/corrected classifications.
- Manual corrections persist in `outputs/video_classification.db`.
- Classification Review explains confidence and evidence.

## Git commands

```bash
git checkout -b feature/video-intelligence
git add radar/scanner.py radar/scoring.py radar/classification_feedback.py radar/classification_web.py app.py
git commit -m "Integrate confidence-based video intelligence"
git push -u origin feature/video-intelligence
```
