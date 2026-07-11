from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import requests
from PIL import Image

from .classification_feedback import get_feedback_for_video, get_label_priors

BASE = Path(__file__).resolve().parents[1]
CACHE_DIR = BASE / "outputs" / "video_intelligence_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

PRIMARY_FORMATS = [
    "interactive_guess",
    "sound_replacement",
    "fact_card",
    "tutorial",
    "secret_reveal",
    "mistake_warning",
    "gameplay_story",
    "challenge",
    "comparison",
    "meme_caption",
    "skit_animation",
    "news_update",
    "manual_review",
]

CONTENT_TYPES = [
    "gameplay",
    "animation",
    "image_slideshow",
    "mixed_edit",
    "unknown",
]

FORMAT_RULES: dict[str, dict[str, float]] = {
    "interactive_guess": {
        "guess": 2.4,
        "which one": 1.8,
        "real voice": 3.0,
        "real sound": 3.0,
        "comment your": 1.2,
        "pick one": 1.5,
        "1 2 3 4": 2.3,
    },
    "sound_replacement": {
        "scream": 2.0,
        "sound": 1.2,
        "voice": 1.0,
        "audio": 1.0,
        "what does": 1.3,
        "sounds like": 2.2,
    },
    "fact_card": {
        "fact": 2.2,
        "did you know": 2.7,
        "older than": 2.2,
        "roblox was": 2.3,
        "history": 1.6,
        "oldest": 1.5,
    },
    "tutorial": {
        "how to": 2.8,
        "guide": 2.0,
        "tips": 1.6,
        "beat": 1.4,
        "stage": 0.8,
        "tutorial": 2.4,
    },
    "secret_reveal": {
        "secret": 2.5,
        "hidden": 2.4,
        "nobody knows": 2.5,
        "easter egg": 2.4,
        "rare": 1.3,
        "found this": 1.2,
    },
    "mistake_warning": {
        "don't": 2.4,
        "never": 1.8,
        "wrong": 2.0,
        "ruin": 2.2,
        "avoid": 1.8,
        "mistake": 2.0,
    },
    "gameplay_story": {
        "then this happened": 2.4,
        "i tried": 1.7,
        "i survived": 2.0,
        "story": 1.0,
        "almost": 1.0,
        "wait for it": 1.5,
    },
    "challenge": {
        "challenge": 2.3,
        "without": 1.3,
        "can i": 1.2,
        "only using": 1.6,
        "impossible": 1.5,
        "speedrun": 1.7,
    },
    "comparison": {
        "vs": 1.5,
        "better": 1.0,
        "before and after": 2.2,
        "old vs new": 2.4,
        "which is better": 2.2,
    },
    "meme_caption": {
        "pov": 2.5,
        "me when": 2.4,
        "bro": 0.8,
        "when your": 1.6,
        "meme": 1.7,
        "relatable": 1.4,
    },
    "skit_animation": {
        "animation": 2.6,
        "animated": 2.6,
        "skit": 2.3,
        "movie": 1.3,
        "roleplay": 1.5,
        "moon animator": 3.0,
        "blender": 3.0,
    },
    "news_update": {
        "update": 2.0,
        "new": 0.7,
        "leaked": 1.8,
        "released": 1.2,
        "patch": 1.4,
        "event": 0.8,
    },
}

HOOK_MAP = {
    "interactive_guess": "interactive_guessing",
    "mistake_warning": "threat_mistake",
    "secret_reveal": "secret_curiosity",
    "fact_card": "fact_curiosity",
    "tutorial": "utility",
    "challenge": "challenge",
    "meme_caption": "pov_meme",
    "news_update": "news_update",
    "gameplay_story": "story",
    "comparison": "comparison",
    "sound_replacement": "audio_curiosity",
    "skit_animation": "skit",
    "manual_review": "unknown",
}


@dataclass
class ClassificationResult:
    video_id: str
    primary_format: str
    secondary_formats: list[str] = field(default_factory=list)
    content_type: str = "unknown"
    hook_type: str = "unknown"
    confidence: int = 0
    needs_review: bool = True
    evidence: list[str] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)
    source: str = "metadata+thumbnail"

    def to_columns(self) -> dict[str, Any]:
        return {
            "primary_format": self.primary_format,
            "secondary_formats": json.dumps(self.secondary_formats, ensure_ascii=False),
            "content_type": self.content_type,
            "classification_confidence": self.confidence,
            "classification_needs_review": self.needs_review,
            "classification_evidence": json.dumps(self.evidence, ensure_ascii=False),
            "classification_scores": json.dumps(self.scores, ensure_ascii=False),
            "hook_type": self.hook_type,
            "template_type": self.primary_format if not self.needs_review else "manual_review",
        }


def _normalize_text(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[^a-z0-9%#' ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _metadata_blob(video: dict[str, Any]) -> tuple[str, list[str]]:
    title = _normalize_text(video.get("title"))
    description = _normalize_text(video.get("description"))
    tags_raw = video.get("tags") or []
    if isinstance(tags_raw, str):
        try:
            parsed = json.loads(tags_raw)
            tags_raw = parsed if isinstance(parsed, list) else [tags_raw]
        except Exception:
            tags_raw = re.split(r"[,;|]", tags_raw)
    tags = [_normalize_text(x) for x in tags_raw if str(x).strip()]
    channel = _normalize_text(video.get("channel_title"))
    return " ".join([title, description, " ".join(tags), channel]), tags


def _thumbnail_cache_path(url: str) -> Path:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"thumb_{digest}.jpg"


def _thumbnail_features(url: str) -> dict[str, float]:
    if not url:
        return {}
    cache = _thumbnail_cache_path(url)
    try:
        if not cache.exists():
            response = requests.get(url, timeout=8)
            response.raise_for_status()
            cache.write_bytes(response.content)
        with Image.open(cache) as img:
            img = img.convert("RGB").resize((160, 90))
            pixels = list(img.getdata())
        if not pixels:
            return {}
        brightness = sum(sum(px) / 3 for px in pixels) / len(pixels)
        saturation = 0.0
        contrast_values = []
        for r, g, b in pixels:
            mx, mn = max(r, g, b), min(r, g, b)
            saturation += 0 if mx == 0 else (mx - mn) / mx
            contrast_values.append((r + g + b) / 3)
        saturation /= len(pixels)
        mean = brightness
        variance = sum((x - mean) ** 2 for x in contrast_values) / len(contrast_values)
        return {
            "thumbnail_brightness": round(brightness, 2),
            "thumbnail_saturation": round(saturation, 4),
            "thumbnail_contrast": round(math.sqrt(variance), 2),
        }
    except Exception:
        return {}


def _format_scores(video: dict[str, Any]) -> tuple[dict[str, float], list[str]]:
    blob, tags = _metadata_blob(video)
    title = _normalize_text(video.get("title"))
    scores = {label: 0.0 for label in PRIMARY_FORMATS if label != "manual_review"}
    evidence: list[str] = []

    for label, rules in FORMAT_RULES.items():
        for phrase, weight in rules.items():
            if phrase in title:
                scores[label] += weight * 1.45
                evidence.append(f"title contains '{phrase}' → {label}")
            elif phrase in blob:
                scores[label] += weight
                evidence.append(f"metadata contains '{phrase}' → {label}")

    # Tags are weaker than title but still useful.
    for tag in tags:
        for label, rules in FORMAT_RULES.items():
            for phrase, weight in rules.items():
                if phrase in tag:
                    scores[label] += weight * 0.55

    duration = int(video.get("duration_seconds") or 0)
    if 0 < duration <= 12:
        scores["interactive_guess"] += 0.4
        scores["meme_caption"] += 0.35
    if duration >= 25:
        scores["gameplay_story"] += 0.35
        scores["tutorial"] += 0.25

    # Animation clues should outweigh generic sound/voice words.
    if any(x in blob for x in ("moon animator", "blender", "animated", "animation", "skit")):
        scores["skit_animation"] += 3.5
        scores["interactive_guess"] *= 0.72
        scores["sound_replacement"] *= 0.72

    # Disambiguation: 'sound' alone must not force Guess Voice.
    if "guess" not in blob and "which one" not in blob and "1 2 3 4" not in blob:
        scores["interactive_guess"] *= 0.45

    # Feedback-derived priors.
    priors = get_label_priors()
    for label, prior in priors.items():
        if label in scores:
            scores[label] += max(-1.0, min(1.0, prior))

    return scores, evidence


def _content_type(video: dict[str, Any], scores: dict[str, float]) -> tuple[str, list[str]]:
    blob, _ = _metadata_blob(video)
    evidence: list[str] = []
    if scores.get("skit_animation", 0) >= 3.0 or any(
        x in blob for x in ("animation", "animated", "moon animator", "blender")
    ):
        evidence.append("animation language detected")
        return "animation", evidence
    if any(x in blob for x in ("slideshow", "images", "picture", "photo")):
        evidence.append("slideshow/image language detected")
        return "image_slideshow", evidence
    if any(x in blob for x in ("gameplay", "roblox", "obby", "stage", "speedrun", "survive")):
        evidence.append("gameplay language detected")
        return "gameplay", evidence
    if max(scores.values() or [0]) >= 2.5:
        return "mixed_edit", evidence
    return "unknown", evidence


def classify_video(video: dict[str, Any], force_refresh: bool = False) -> ClassificationResult:
    video_id = str(video.get("video_id") or "unknown")
    feedback = get_feedback_for_video(video_id)
    if feedback and feedback.get("correct_label"):
        label = feedback["correct_label"]
        return ClassificationResult(
            video_id=video_id,
            primary_format=label,
            secondary_formats=[],
            content_type=feedback.get("content_type") or "unknown",
            hook_type=HOOK_MAP.get(label, "unknown"),
            confidence=100,
            needs_review=False,
            evidence=["manually corrected by user"],
            scores={label: 100.0},
            source="manual_feedback",
        )

    scores, evidence = _format_scores(video)
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_label, best_score = ranked[0] if ranked else ("manual_review", 0.0)
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = best_score - second_score

    content_type, content_evidence = _content_type(video, scores)
    evidence.extend(content_evidence)

    # Confidence uses strength and separation, not fake certainty.
    confidence = int(max(0, min(99, round(22 + best_score * 12 + margin * 8))))
    if best_score < 1.75:
        best_label = "manual_review"
        confidence = min(confidence, 44)
    needs_review = best_label == "manual_review" or confidence < 68 or margin < 0.8

    secondary = [
        label
        for label, score in ranked[1:4]
        if score >= max(1.25, best_score * 0.48)
    ]

    # Keep the evidence readable.
    deduped_evidence = []
    seen = set()
    for item in evidence:
        if item not in seen:
            deduped_evidence.append(item)
            seen.add(item)
        if len(deduped_evidence) >= 8:
            break

    return ClassificationResult(
        video_id=video_id,
        primary_format=best_label,
        secondary_formats=secondary,
        content_type=content_type,
        hook_type=HOOK_MAP.get(best_label, "unknown"),
        confidence=confidence,
        needs_review=needs_review,
        evidence=deduped_evidence or ["insufficient metadata evidence"],
        scores={k: round(v, 3) for k, v in ranked},
    )


def enrich_video(video: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(video)
    result = classify_video(enriched)
    enriched.update(result.to_columns())
    enriched.update(_thumbnail_features(str(video.get("thumbnail") or "")))
    return enriched
