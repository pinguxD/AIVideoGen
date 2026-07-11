# Reference Learning Pipeline

This package adds two separate workflows:

1. **AI Reference Scout**  
   It automatically chooses which discovered viral Shorts are most useful for
   the system to learn from.

2. **Batch Full-Video Analysis**  
   Drop permitted local reference files into one folder and analyze all of them
   in one command. Each processed file is moved away automatically.

## Required existing modules

This package expects these earlier modules to exist:

```text
radar/full_video_analyzer.py
radar/production_planner.py
```

## Copy files

Copy into your project:

```text
radar/reference_library.py
radar/reference_scout.py
batch_analyze_references.py
scout_references.py
```

## Folder structure

The code creates:

```text
assets/reference_videos/
├── pending/
├── analyzed/
└── failed/
```

Place videos you are allowed to analyze in:

```text
assets/reference_videos/pending/
```

## Analyze every pending video at once

```powershell
py batch_analyze_references.py
```

Successful files move to:

```text
assets/reference_videos/analyzed/
```

Failed files move to:

```text
assets/reference_videos/failed/
```

Failures also receive:

```text
<filename>.error.txt
```

Reports are written to:

```text
outputs/reference_reports/
```

For every analyzed file:

```text
<name>.analysis.json
<name>.plan.json
<name>.why_viral.md
```

A run history is stored in:

```text
outputs/reference_library.db
```

## Let AI choose learning candidates

First run the normal trend scan:

```powershell
py trend_radar.py
```

Then:

```powershell
py scout_references.py --limit 25
```

The AI ranks candidates using:

- recent view velocity;
- views per subscriber;
- format novelty;
- recreation potential;
- classification confidence.

The queue is stored in:

```text
outputs/reference_queue.db
```

## Recommended workflow

For the first stage:

1. Let Reference Scout identify the best 10–25 candidates.
2. Manually approve only references that fit the channel and workflow.
3. Add permitted local files for those approved references to `pending/`.
4. Run the batch analyzer.
5. Review the generated `why_viral.md` and production plans.
6. Use your corrections to improve classifiers and planners.

This avoids blindly collecting hundreds of low-quality examples.

## Important limitation

Reference Scout can automatically discover and rank videos from your Trend Radar
data. The official YouTube Data API does not provide the actual video media file,
so full frame/audio analysis still requires a permitted local media file.

The system should learn the structure and recreate it with your own assets. It
should not silently reuse third-party footage.
