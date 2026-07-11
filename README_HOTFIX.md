# Story Scout v1.1 hotfix

This fixes the `/story-scout` Internal Server Error caused by old v1
`story_candidates.json` records not containing the new v1.1 fields:

- `english_confidence`
- `detected_game`

Replace:

```text
radar/story_scout.py
```

Then restart:

```powershell
Ctrl + C
py app.py
```

Your old approvals, rejections and imported-reference records are preserved.
The page will migrate older rows in memory and calculate the missing fields.
