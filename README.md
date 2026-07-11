# Analysis → Creator AI Bridge

Copy these two files into `radar/`:

```text
analysis_to_creator.py
analysis_review_web.py
```

The second file replaces the existing `analysis_review_web.py`.

Restart:

```powershell
Ctrl + C
py app.py
```

Open an analyzed reference, verify/correct it, save the correction, then click:

```text
Create project from analysis
```

## Behavior

- Reads the corrected production plan.
- Selects gameplay through Clip Brain.
- Searches/downloads sounds only for:
  - interactive guessing;
  - sound replacement;
  - meme edit when the plan explicitly enables a soundboard.
- Does not attach random sounds to fact/story/caption videos.
- Creates a normal Creator AI project JSON.
- Redirects to the Creator AI review page.
- Shows exact missing inputs.
- Keeps narrated formats as `NEEDS_ASSETS` until script, voiceover, caption and
  visual-insert generation exist.
- Only existing renderer-ready formats can become `AUTO_READY`.

## Expected output

```text
outputs/creator_projects/reference_<video-name>.json
```

Narrated fact/list example:

```text
Status: NEEDS_ASSETS
Missing:
- original verified fact/list script
- AI voice or human voice selection
- timed captions
- relevant image/meme inserts for each fact
```
