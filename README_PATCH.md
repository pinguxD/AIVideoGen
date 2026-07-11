# Clip Brain v1 patch

This patch adds:

- Cached visual metadata for every mined clip.
- Context requirements derived from the inspiration title/template.
- Clip ranking based on framing, UI risk, pacing, duration, ratings, filename/context clues, and your prior feedback.
- Explainable match score, reasons, and warnings on Creator AI projects.
- Context-specific feedback controls: fits, wrong character/action, character not visible, too much UI, poor framing, does not fit, and global never-use.
- A concrete recording task when no library clip passes the confidence threshold.
- Backward-compatible CreatorProject loading.
- Default miner cap of 30 clips per source recording.

## Apply

Copy this patch folder anywhere, open Git Bash or PowerShell in your AIVideoGen project root, and run:

```powershell
py "PATH_TO_PATCH/apply_clip_brain_patch.py"
```

Or copy `apply_clip_brain_patch.py` and the included `radar/clip_brain.py` into your project root temporarily, then run:

```powershell
py apply_clip_brain_patch.py
```

Restart:

```powershell
py app.py
```

The first project analysis after installation can be slower because Clip Brain analyzes and caches each mined video. Later analyses reuse `outputs/clip_brain.db`.

## Commit

```bash
git checkout -b feature/clip-brain
git add radar/clip_brain.py radar/creator_projects.py radar/creator_web.py radar/gameplay_miner.py
git commit -m "Add context-aware Clip Brain"
git push -u origin feature/clip-brain
```
