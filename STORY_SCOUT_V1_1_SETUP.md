# Story Scout v1.1 — English Roblox & Minecraft Only

This update narrows discovery to the formats you actually want.

## Filters

Every result must now pass all of these:

```text
Duration: 8–60 seconds
Minimum views: chosen in dashboard
Storytelling relevance: required
Game background: Roblox or Minecraft only
YouTube relevance language: English
Local English confidence: at least 62%
```

The local language filter checks:

- Latin/ASCII text ratio;
- common English words;
- common non-English markers;
- Cyrillic, Arabic, Hindi, Japanese and Chinese scripts.

This is stricter than YouTube's `relevanceLanguage` parameter, which is only a
search relevance hint and not a guarantee that every result is English.

## Optimized default searches

```text
minecraft parkour storytime shorts english
minecraft reddit story shorts english
roblox storytime shorts english
roblox reddit story gameplay shorts english
minecraft gameplay confession story shorts
roblox gameplay story shorts
```

## Dashboard

Open:

```text
http://127.0.0.1:5000/story-scout
```

Each candidate now shows:

```text
English confidence
Detected game: Roblox or Minecraft
Storytelling score
Gaming score
Viral score
Opportunity score
```

Use 2–4 queries per scan to preserve YouTube API quota.
