from __future__ import annotations

import math

from .video_intelligence import classify_video

HARD_TO_CREATE = [
    "animation", "animated", "movie", "roleplay", "blender",
    "studio animation", "moon animator", "roblox studio", "custom", "skit",
]
EASY_TEMPLATES = {
    "interactive_guess", "sound_replacement", "fact_card", "tutorial",
    "secret_reveal", "mistake_warning", "challenge", "comparison", "meme_caption",
}
GAME_HINTS = [
    "animal hospital", "grow a garden", "99 nights", "steal a brainrot", "doors",
    "pressure", "forsaken", "keyboard escape", "fish it", "slime rng", "roblox",
]


def text_blob(v: dict) -> str:
    tags = v.get("tags") or []
    if isinstance(tags, list):
        tags = " ".join(str(x) for x in tags)
    return " ".join(str(v.get(k, "")) for k in ["title", "description", "channel_title"]) + " " + str(tags)


def classify_hook(title: str) -> str:
    result = classify_video({"video_id": "adhoc", "title": title})
    return result.hook_type


def detect_game(v: dict) -> str:
    blob = text_blob(v).lower()
    for game in GAME_HINTS:
        if game in blob:
            return game.title()
    return "Roblox"


def template_type(v: dict) -> str:
    return classify_video(v).primary_format


def production_score(v: dict) -> tuple[int, str, str, str, str]:
    blob = text_blob(v).lower()
    result = classify_video(v)
    score = 48
    reasons: list[str] = []
    missing: list[str] = []
    tools = ["Roblox", "CapCut"]

    if result.primary_format in EASY_TEMPLATES and not result.needs_review:
        score += 28
        reasons.append(f"supported {result.primary_format} format")
    elif result.needs_review:
        score -= 18
        missing.append("manual classification review")
        reasons.append("classification confidence is too low")

    if result.content_type == "animation" or any(x in blob for x in HARD_TO_CREATE):
        score -= 42
        missing.append("possible custom animation/studio work")
    if int(v.get("duration_seconds") or 0) and int(v.get("duration_seconds")) <= 20:
        score += 8
        reasons.append("short runtime")
    if int(v.get("subscriber_count") or 0) < 10000:
        score += 5
        reasons.append("small creator proof")

    score = max(0, min(100, score))
    verdict = "MAKE" if score >= 75 else ("REVIEW" if score >= 50 else "SKIP")
    return score, verdict, ", ".join(tools), "; ".join(missing) or "none", "; ".join(reasons) or "needs review"


def auto_recreate(v: dict, asset_index: dict | None = None) -> tuple[int, str, str, str, str]:
    asset_index = asset_index or {}
    result = classify_video(v)
    tmpl = result.primary_format

    if result.needs_review:
        return 20, "MANUAL ONLY", "manual_review", "classification review", "low-confidence or ambiguous format"

    base_scores = {
        "interactive_guess": 82,
        "sound_replacement": 80,
        "fact_card": 78,
        "tutorial": 68,
        "secret_reveal": 75,
        "mistake_warning": 72,
        "challenge": 58,
        "comparison": 62,
        "meme_caption": 70,
        "gameplay_story": 42,
        "skit_animation": 18,
        "news_update": 55,
        "manual_review": 20,
    }
    base = base_scores.get(tmpl, 25)
    required: list[str] = []
    missing: list[str] = []

    if tmpl in {"interactive_guess", "sound_replacement"}:
        required = ["relevant source clip/image", "3-4 distinct meme sounds"]
        if not asset_index.get("source"):
            missing.append("relevant source clip")
        if asset_index.get("sounds", 0) < 3:
            missing.append("3+ sounds")
    elif tmpl in {"fact_card", "tutorial", "secret_reveal", "mistake_warning", "meme_caption", "news_update"}:
        required = ["background gameplay", "script/caption"]
        if not asset_index.get("source"):
            missing.append("background gameplay")
    else:
        required = ["manual project definition"]
        missing.append("template not safely supported")

    if result.content_type == "animation":
        base -= 45
        missing.append("likely custom animation")
    if missing:
        base -= min(30, len(missing) * 9)

    score = max(0, min(100, base))
    verdict = "AUTO CREATE" if score >= 85 and not missing else ("NEEDS ASSETS" if score >= 45 else "MANUAL ONLY")
    return score, verdict, tmpl, "; ".join(required), "; ".join(missing) or "none"


def opportunity_score(v: dict, prod_score: int, auto_score: int) -> int:
    views = max(1, int(v.get("view_count") or 0))
    subs = max(1, int(v.get("subscriber_count") or 1))
    age = max(0.1, float(v.get("age_days") or 1))
    views_per_day = views / age
    views_per_sub = views / subs
    velocity = min(100, math.log10(views_per_day + 10) * 25)
    small_creator = min(100, math.log10(views_per_sub + 1) * 45)
    confidence = float(v.get("classification_confidence") or 0)
    trust_multiplier = 0.55 + 0.45 * (confidence / 100)
    score = (0.35 * velocity + 0.25 * small_creator + 0.20 * prod_score + 0.20 * auto_score) * trust_multiplier
    return int(max(0, min(100, score)))


def viral_dna(v: dict) -> str:
    result = classify_video(v)
    parts = [result.hook_type, result.primary_format, result.content_type, detect_game(v)]
    duration = int(v.get("duration_seconds") or 0)
    if duration:
        parts.append(f"{duration}s")
    return " + ".join(parts)


def title_variants(v: dict) -> str:
    game = detect_game(v)
    tmpl = template_type(v)
    if tmpl == "interactive_guess":
        return f"Guess The REAL {game} Voice..., Can You Guess The Correct Sound?..., Comment Before The Reveal..."
    if tmpl in {"fact_card", "secret_reveal"}:
        return "99% Of Players Don't Know This..., This Roblox Fact Is Weird..., Nobody Noticed This..."
    if tmpl == "mistake_warning":
        return "You've Been Doing This Wrong..., Never Do This In Roblox..., This One Mistake Ruins Everything..."
    return "Wait... This Is Roblox?, Nobody Expected This..., I Bet You Get This Wrong..."
