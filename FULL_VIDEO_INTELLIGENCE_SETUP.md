# Full Video Intelligence v1

This is the first version that analyzes the **actual full video file** instead of
only using its YouTube title, description, tags, and thumbnail.

## Important input rule

The YouTube Data API does not return the video media file. Put a local reference
video that you own, created, downloaded with permission, or are otherwise allowed
to analyze in:

```text
assets/reference_videos/
```

Do not make automatic reuse of third-party footage the default. The system should
recreate the format from your own assets and tell you what is missing.

## Install

Add this to `requirements.txt`:

```text
opencv-python-headless==4.10.0.84
```

Then:

```powershell
py -m pip install opencv-python-headless==4.10.0.84
```

FFmpeg and FFprobe must be available on PATH.

## Copy files

Copy:

```text
radar/full_video_analyzer.py
radar/production_planner.py
analyze_reference.py
```

into the matching project locations.

## Use

```powershell
py analyze_reference.py "assets/reference_videos/reference.mp4" --title "These Facts Could Save Your Life"
```

Outputs:

```text
outputs/reference_analysis/<video>.analysis.json
outputs/production_plans/<video>.plan.json
```

## What it analyzes now

- the full runtime and dimensions;
- scene changes and cut frequency;
- motion;
- estimated on-screen-text density;
- probable image/meme insert sections;
- speech/narration ratio;
- silence ratio;
- isolated sound-effect peaks;
- probable voiceover;
- conservative probable-synthetic-voice warning;
- local meme-template similarity;
- local sound-library spectral similarity;
- the likely production format;
- what the program already has;
- exactly what must be supplied before recreation.

## Formats planned in v1

- narrated fact/list video;
- narrated story;
- interactive guessing;
- sound replacement;
- meme edit;
- gameplay-caption video;
- complex/manual review.

## Honest limitations

- Synthetic/AI voice detection is only a heuristic and is explicitly confidence-limited.
- It does not identify arbitrary meme templates by name unless reference images are
  added to `assets/meme_templates/`.
- Exact sound identification in mixed audio is difficult. v1 checks local-library
  spectral similarity and isolated sound events; it does not claim perfect
  fingerprinting.
- Text density is detected structurally. It does not run OCR in this version.
- The existing renderer is not yet connected to every plan type. First verify that
  the extracted plan is correct, then add renderers per supported format.
