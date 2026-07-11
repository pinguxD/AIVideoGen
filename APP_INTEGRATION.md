# Analysis Correction System integration

## Required previous modules

The following modules must already exist:

```text
radar/full_video_analyzer.py
radar/production_planner.py
radar/reference_library.py
```

## Copy these new files

```text
radar/analysis_feedback.py
radar/analysis_review.py
radar/analysis_review_web.py
```

## Add navigation

In `app.py`, add:

```python
("/analysis-review", "Analysis Review"),
```

A sensible location:

```python
("/reference-queue", "Reference Queue"),
("/analysis-review", "Analysis Review"),
("/sound-library", "Sound Library"),
```

## Register routes

Near the bottom of `app.py`:

```python
from radar.analysis_review_web import register_analysis_review_routes

register_analysis_review_routes(
    app,
    page,
    esc,
)
```

## Start

```powershell
py app.py
```

Open:

```text
http://127.0.0.1:5000/analysis-review
```

## What gets stored

Corrections database:

```text
outputs/analysis_feedback.db
```

Corrected outputs:

```text
outputs/corrected_reference_analysis/
├── <reference>.corrected.analysis.json
└── <reference>.corrected.plan.json
```

The corrected production plan explicitly overrides incompatible automatic choices.
For example, correcting a video to `narrated_fact_list` forces `soundboard = false`.
