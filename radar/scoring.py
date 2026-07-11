from __future__ import annotations

import math
import re
from typing import Any

HARD_TO_CREATE = [
    "animation",
    "animated",
    "movie",
    "story",
    "roleplay",
    "blender",
    "studio animation",
    "moon animator",
    "roblox studio",
    "custom",
    "skit",
]

EASY_TERMS = [
    "guess",
    "voice",
    "sound",
    "meme",
    "fact",
    "secret",
    "did you know",
    "pov",
    "which",
    "comment",
    "roblox facts",
]

GAME_HINTS = [
    "animal hospital",
    "grow a garden",
    "99 nights",
    "steal a brainrot",
    "doors",
    "pressure",
    "forsaken",
    "keyboard escape",
    "fish it",
    "slime rng",
    "roblox",
]

# Video Intelligence labels -> renderer/production template families.
TEMPLATE_ALIASES = {
    "interactive_guess": "guess_voice",
    "guess_voice": "guess_voice",
    "sound_replacement": "sound_replacement",
    "fact_card": "fact_card",
    "secret_reveal": "fact_card",
    "mistake_warning": "fact_card",
    "news_update": "fact_card",
    "meme_caption": "meme_caption",
    "tutorial": "manual_review",
    "gameplay_story": "manual_review",
    "challenge": "manual_review",
    "comparison": "manual_review",
    "skit_animation": "manual_review",
    "manual_review": "manual_review",
}

SUPPORTED_AUTO = {
    "guess_voice",
    "sound_replacement",
    "fact_card",
    "meme_caption",
}


def text_blob(video: dict[str, Any]) -> str:
    tags = video.get("tags", "")
    return " ".join(
        str(video.get(key, ""))
        for key in ("title", "description", "channel_title")
    ).lower() + " " + str(tags).lower()


def classify_hook(title: str) -> str:
    text = title.lower()
    if "guess" in text or "which" in text or "real voice" in text:
        return "interactive_guessing"
    if "don't" in text or "never" in text or "wrong" in text:
        return "threat_mistake"
    if "secret" in text or "hidden" in text or "nobody" in text:
        return "secret_curiosity"
    if "oldest" in text or "older than" in text or "remember" in text:
        return "nostalgia_fact"
    if "rare" in text or "0.0" in text or "1%" in text or "99%" in text:
        return "rarity"
    if "pov" in text:
        return "pov_meme"
    return "general_curiosity"


def detect_game(video: dict[str, Any]) -> str:
    blob = text_blob(video)
    for game in GAME_HINTS:
        if game in blob:
            return game.title()
    return "Roblox"


def template_type(video: dict[str, Any]) -> str:
    """Respect Video Intelligence before falling back to old keyword logic."""
    classified = str(
        video.get("primary_format")
        or video.get("template_type")
        or ""
    ).strip()
    if classified:
        return TEMPLATE_ALIASES.get(classified, classified)

    blob = text_blob(video)
    if "guess" in blob and any(
        phrase in blob for phrase in ("voice", "sound", "scream", "which one")
    ):
        return "guess_voice"
    if any(phrase in blob for phrase in ("scream", "funny sound", "audio")):
        return "sound_replacement"
    if any(
        phrase in blob
        for phrase in ("fact", "did you know", "older than", "secret")
    ):
        return "fact_card"
    if any(phrase in blob for phrase in ("pov", "me when", "meme")):
        return "meme_caption"
    return "manual_review"


def production_score(
    video: dict[str, Any],
) -> tuple[int, str, str, str, str]:
    blob = text_blob(video)
    template = template_type(video)
    score = 50
    reasons: list[str] = []
    missing: list[str] = []
    tools = ["Roblox", "CapCut"]

    if any(term in blob for term in EASY_TERMS):
        score += 20
        reasons.append("simple hook/template")

    if any(term in blob for term in HARD_TO_CREATE):
        score -= 45
        missing.append("possible custom animation/studio work")

    if template in SUPPORTED_AUTO:
        score += 25
        reasons.append(f"fits {template} template")
    else:
        score -= 20
        missing.append("template is not yet supported by Auto Studio")

    if bool(video.get("classification_needs_review")):
        score -= 30
        missing.append("classification needs manual review")

    confidence = int(video.get("classification_confidence") or 0)
    if confidence >= 85:
        score += 5
        reasons.append("high classification confidence")
    elif confidence and confidence < 68:
        score -= 15

    duration = int(video.get("duration_seconds") or 0)
    if duration and duration <= 20:
        score += 10
        reasons.append("short format")

    if int(video.get("subscriber_count") or 0) < 10000:
        score += 5
        reasons.append("small creator proof")

    score = max(0, min(100, score))
    verdict = "MAKE" if score >= 75 else ("REVIEW" if score >= 50 else "SKIP")
    return (
        score,
        verdict,
        ", ".join(tools),
        "; ".join(dict.fromkeys(missing)) if missing else "none",
        "; ".join(reasons) if reasons else "needs manual review",
    )


def auto_recreate(
    video: dict[str, Any],
    asset_index: dict | None = None,
) -> tuple[int, str, str, str, str]:
    asset_index = asset_index or {}
    template = template_type(video)
    blob = text_blob(video)
    missing: list[str] = []
    required: list[str] = []

    base_scores = {
        "guess_voice": 82,
        "sound_replacement": 80,
        "fact_card": 78,
        "meme_caption": 70,
        "manual_review": 20,
    }
    score = base_scores.get(template, 20)

    if bool(video.get("classification_needs_review")):
        score = min(score, 30)
        missing.append("correct the video classification first")

    if template in {"guess_voice", "sound_replacement"}:
        required = ["source clip/image of character", "3-4 meme sounds"]
        if not asset_index.get("source"):
            missing.append(
                "run raw gameplay miner / source clip not mined yet"
                if asset_index.get("raw_gameplay", 0)
                else "source clip/image or raw gameplay"
            )
        if asset_index.get("sounds", 0) < 3:
            missing.append("3+ sounds (Sound Finder can search)")
    elif template == "fact_card":
        required = ["background gameplay clip", "verified fact/script text"]
        if not asset_index.get("source"):
            missing.append(
                "run raw gameplay miner / background clip not mined yet"
                if asset_index.get("raw_gameplay", 0)
                else "background gameplay or raw gameplay"
            )
    elif template == "meme_caption":
        required = ["background clip/image", "caption", "meme sound optional"]
        if not asset_index.get("source"):
            missing.append("background clip/image or raw gameplay")
    else:
        required = ["manual review"]
        missing.append("template not supported")

    if any(term in blob for term in HARD_TO_CREATE):
        score -= 45
        missing.append("likely animation/custom scene")

    if missing:
        score -= min(25, len(missing) * 8)

    score = max(0, min(100, score))
    verdict = (
        "AUTO CREATE"
        if score >= 85 and not missing
        else ("NEEDS ASSETS" if score >= 45 else "MANUAL ONLY")
    )
    return (
        score,
        verdict,
        template,
        "; ".join(required),
        "; ".join(dict.fromkeys(missing)) if missing else "none",
    )


def opportunity_score(
    video: dict[str, Any],
    prod_score: int,
    auto_score: int,
) -> int:
    views = max(1, int(video.get("view_count") or 0))
    subscribers = max(1, int(video.get("subscriber_count") or 1))
    age = max(0.1, float(video.get("age_days") or 1))
    views_per_day = views / age
    views_per_sub = views / subscribers

    velocity = min(100, math.log10(views_per_day + 10) * 25)
    small_creator = min(100, math.log10(views_per_sub + 1) * 45)
    confidence = int(video.get("classification_confidence") or 0)

    score = (
        0.33 * velocity
        + 0.23 * small_creator
        + 0.20 * prod_score
        + 0.19 * auto_score
        + 0.05 * confidence
    )
    if bool(video.get("classification_needs_review")):
        score *= 0.72
    return int(max(0, min(100, score)))


def viral_dna(video: dict[str, Any]) -> str:
    hook = str(video.get("hook_type") or classify_hook(video.get("title", "")))
    parts = [hook, template_type(video), detect_game(video)]
    duration = int(video.get("duration_seconds") or 0)
    if duration:
        parts.append(f"{duration}s")
    return " + ".join(parts)


def title_variants(video: dict[str, Any]) -> str:
    game = detect_game(video)
    template = template_type(video)
    if template == "guess_voice":
        return (
            f"Guess The REAL {game} Voice..., "
            "Nobody Expected This Voice..., "
            "Comment Before The Reveal..."
        )
    if template == "fact_card":
        return (
            "99% Of Players Dont Know This..., "
            "This Roblox Fact Is Weird..., "
            "Youve Been Lied To About Roblox..."
        )
    return "Wait... This Is Roblox?, Nobody Expected This..., I Bet You Get This Wrong..."
