# Story Scout v1.2 — Strict Search

This update fixes the two quality problems:

1. Non-English results slipping through.
2. Unrelated videos passing because the search query itself contained
   “Roblox” or “Minecraft”.

## Search restrictions

YouTube search now uses:

```text
relevanceLanguage=en
videoCategoryId=20  (Gaming)
safeSearch=strict
videoDuration=short
```

The default searches use quoted game phrases.

## Strict result validation

A candidate is accepted only when:

```text
The video's own title, description, tags or channel name
explicitly identifies Roblox or Minecraft

AND

defaultAudioLanguage/defaultLanguage is English
OR a strict local English test scores at least 76%
```

The search query is no longer counted as proof of the game background.

## Rejected references

Rejected videos are permanently hidden from the normal Story Scout page.
Their records remain in the JSON database so future scans remember not to
show them again.

## Replace project and restart

```powershell
Ctrl + C
py app.py
```

Then run a new scan from:

```text
http://127.0.0.1:5000/story-scout
```

Because the filter is much stricter, fewer results are expected. Those results
should be substantially more relevant.
