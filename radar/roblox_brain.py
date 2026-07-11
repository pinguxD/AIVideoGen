from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .analysis_review import load_review_bundle
from .full_video_analyzer import BASE

OUTPUT_DIR = BASE / "outputs" / "roblox_brain"
RECREATION_DIR = BASE / "outputs" / "recreation_intelligence"


SCENE_LIBRARY: dict[str, dict[str, Any]] = {
    "simple_platform": {
        "keywords": ["platform", "baseplate", "showcase", "character"],
        "tags": ["generic", "showcase"],
        "complexity": 1,
        "builder_id": "scene.simple_platform.v1",
    },
    "simple_obby": {
        "keywords": ["obby", "obstacle", "jump", "parkour", "stage"],
        "tags": ["obby", "movement"],
        "complexity": 2,
        "builder_id": "scene.simple_obby.v1",
    },
    "hospital": {
        "keywords": ["hospital", "doctor", "nurse", "patient", "clinic"],
        "tags": ["indoor", "roleplay"],
        "complexity": 3,
        "builder_id": "scene.hospital.v1",
    },
    "city": {
        "keywords": ["city", "street", "road", "building", "town"],
        "tags": ["outdoor", "urban"],
        "complexity": 3,
        "builder_id": "scene.city.v1",
    },
    "horror_corridor": {
        "keywords": ["horror", "dark hallway", "corridor", "monster", "scary"],
        "tags": ["horror", "indoor"],
        "complexity": 3,
        "builder_id": "scene.horror_corridor.v1",
    },
    "character_showcase": {
        "keywords": ["avatar", "character", "head", "body", "size", "scale"],
        "tags": ["avatar", "showcase"],
        "complexity": 2,
        "builder_id": "scene.character_showcase.v1",
    },
}

MECHANIC_LIBRARY: dict[str, dict[str, Any]] = {
    "none": {
        "keywords": [],
        "builder_id": "mechanic.none.v1",
        "procedural": True,
        "complexity": 0,
    },
    "grow": {
        "keywords": ["grow", "bigger", "giant", "increase size", "679%", "oversized"],
        "builder_id": "mechanic.grow.v1",
        "procedural": True,
        "complexity": 1,
    },
    "shrink": {
        "keywords": ["shrink", "smaller", "tiny", "decrease size"],
        "builder_id": "mechanic.shrink.v1",
        "procedural": True,
        "complexity": 1,
    },
    "walk": {
        "keywords": ["walk", "walking", "move forward", "run"],
        "builder_id": "mechanic.walk.v1",
        "procedural": True,
        "complexity": 1,
    },
    "chase": {
        "keywords": ["chase", "chasing", "follow player", "monster follows"],
        "builder_id": "mechanic.chase.v1",
        "procedural": True,
        "complexity": 2,
    },
    "press_button": {
        "keywords": ["button", "press", "click", "switch"],
        "builder_id": "mechanic.press_button.v1",
        "procedural": True,
        "complexity": 1,
    },
    "spawn_object": {
        "keywords": ["spawn", "appears", "create object", "summon"],
        "builder_id": "mechanic.spawn_object.v1",
        "procedural": True,
        "complexity": 2,
    },
    "reveal_object": {
        "keywords": ["reveal", "secret", "hidden", "show object"],
        "builder_id": "mechanic.reveal_object.v1",
        "procedural": True,
        "complexity": 1,
    },
    "game_specific_unknown": {
        "keywords": ["game-specific", "exact mechanic", "live server", "rare event"],
        "builder_id": "mechanic.custom_required",
        "procedural": False,
        "complexity": 5,
    },
}

CAMERA_LIBRARY: dict[str, dict[str, Any]] = {
    "static": {
        "keywords": ["static", "still camera"],
        "builder_id": "camera.static.v1",
    },
    "third_person_follow": {
        "keywords": ["third person", "follow", "rear camera", "behind avatar"],
        "builder_id": "camera.third_person_follow.v1",
    },
    "rear_closeup": {
        "keywords": ["close-up", "closeup", "rear close", "head focus"],
        "builder_id": "camera.rear_closeup.v1",
    },
    "orbit": {
        "keywords": ["orbit", "rotate around", "camera circles"],
        "builder_id": "camera.orbit.v1",
    },
    "push_in": {
        "keywords": ["push-in", "push in", "slow zoom", "zoom toward"],
        "builder_id": "camera.push_in.v1",
    },
}

UI_LIBRARY: dict[str, dict[str, Any]] = {
    "none": {
        "keywords": [],
        "builder_id": "ui.none.v1",
    },
    "size_slider": {
        "keywords": ["size slider", "slider", "scale ui", "size:"],
        "builder_id": "ui.size_slider.v1",
    },
    "counter": {
        "keywords": ["counter", "count", "number display"],
        "builder_id": "ui.counter.v1",
    },
    "warning_label": {
        "keywords": ["warning", "danger", "alert"],
        "builder_id": "ui.warning_label.v1",
    },
    "arrow": {
        "keywords": ["arrow", "red arrow"],
        "builder_id": "ui.arrow.v1",
    },
    "circle_highlight": {
        "keywords": ["circle", "red circle", "highlight"],
        "builder_id": "ui.circle_highlight.v1",
    },
}


@dataclass
class BrainChoice:
    value: str
    confidence: int
    builder_id: str
    evidence: list[str] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)


@dataclass
class RobloxBrainPlan:
    source_name: str
    scene: BrainChoice
    mechanic: BrainChoice
    camera: BrainChoice
    ui: list[BrainChoice]
    duration: float
    avatar_count: int
    lighting: str
    procedural: bool
    required_assets: list[str]
    blocked_reasons: list[str]
    overall_confidence: int
    generation_mode: str
    builder_sequence: list[str]
    notes: list[str] = field(default_factory=list)

    def save(self) -> Path:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        safe = _safe_name(self.source_name)
        path = OUTPUT_DIR / f"{safe}.roblox_brain.json"
        path.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path


def _safe_name(value: str | Path) -> str:
    return "".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in Path(str(value)).stem
    ).strip("_") or "reference"


def _load_recreation_bundle(source_name: str) -> dict[str, Any]:
    safe = _safe_name(source_name)
    exact = RECREATION_DIR / f"{safe}.recreation_bundle.json"
    if exact.exists():
        return json.loads(exact.read_text(encoding="utf-8"))

    candidates = sorted(
        RECREATION_DIR.glob(f"{safe}*.recreation_bundle.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return {}
    return json.loads(candidates[0].read_text(encoding="utf-8"))


def _collect_context(
    source_name: str,
    recreation_bundle: dict[str, Any],
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    review = load_review_bundle(source_name)
    correction = review.get("correction") or {}
    plan = review.get("plan") or {}
    analysis = review.get("analysis") or {}

    scene_spec = recreation_bundle.get("scene_spec") or {}
    decomposition = recreation_bundle.get("decomposition") or {}

    fragments = [
        source_name,
        str(correction.get("notes") or ""),
        str(correction.get("corrected_format") or ""),
        str(correction.get("hook_type") or ""),
        str(correction.get("video_goal") or ""),
        str(correction.get("emotion") or ""),
        str(correction.get("ending_type") or ""),
        str(correction.get("voice_style") or ""),
        str(plan.get("detected_format") or ""),
        str(analysis.get("source_file") or ""),
        json.dumps(scene_spec, ensure_ascii=False),
    ]
    return " ".join(fragments).lower(), scene_spec, decomposition


def _score_library(
    context: str,
    library: dict[str, dict[str, Any]],
    default_value: str,
) -> BrainChoice:
    scored: list[tuple[int, str, list[str]]] = []

    for value, metadata in library.items():
        evidence: list[str] = []
        score = 0

        for keyword in metadata.get("keywords", []):
            if keyword and keyword.lower() in context:
                score += 22
                evidence.append(f"matched keyword: {keyword}")

        if value == default_value:
            score += 8

        scored.append((score, value, evidence))

    scored.sort(reverse=True)
    best_score, best_value, best_evidence = scored[0]

    if best_score <= 8:
        best_value = default_value
        metadata = library[best_value]
        best_score = 45
        best_evidence = ["safe procedural fallback"]

    alternatives = [
        value
        for score, value, _ in scored[1:4]
        if score > 8 and value != best_value
    ]

    confidence = max(35, min(96, 48 + best_score))
    return BrainChoice(
        value=best_value,
        confidence=confidence,
        builder_id=str(library[best_value]["builder_id"]),
        evidence=best_evidence,
        alternatives=alternatives,
    )


def _infer_ui(context: str) -> list[BrainChoice]:
    choices: list[BrainChoice] = []

    for value, metadata in UI_LIBRARY.items():
        if value == "none":
            continue

        evidence = [
            f"matched keyword: {keyword}"
            for keyword in metadata.get("keywords", [])
            if keyword.lower() in context
        ]
        if evidence:
            choices.append(
                BrainChoice(
                    value=value,
                    confidence=min(95, 60 + len(evidence) * 18),
                    builder_id=str(metadata["builder_id"]),
                    evidence=evidence,
                )
            )

    if not choices:
        choices.append(
            BrainChoice(
                value="none",
                confidence=80,
                builder_id=str(UI_LIBRARY["none"]["builder_id"]),
                evidence=["no required interactive UI detected"],
            )
        )

    return choices


def build_roblox_brain_plan(source_name: str) -> RobloxBrainPlan:
    recreation_bundle = _load_recreation_bundle(source_name)
    context, scene_spec, decomposition = _collect_context(
        source_name,
        recreation_bundle,
    )

    scene = _score_library(
        context,
        SCENE_LIBRARY,
        default_value="simple_platform",
    )
    mechanic = _score_library(
        context,
        MECHANIC_LIBRARY,
        default_value="none",
    )
    camera = _score_library(
        context,
        CAMERA_LIBRARY,
        default_value="third_person_follow",
    )
    ui = _infer_ui(context)

    if "character_showcase" in context or "head" in context or "avatar" in context:
        scene = BrainChoice(
            value="character_showcase",
            confidence=max(scene.confidence, 88),
            builder_id=SCENE_LIBRARY["character_showcase"]["builder_id"],
            evidence=list(dict.fromkeys([
                *scene.evidence,
                "avatar/body transformation context",
            ])),
            alternatives=scene.alternatives,
        )

    if any(token in context for token in ("679%", "oversized", "giant", "grow", "size increase")):
        mechanic = BrainChoice(
            value="grow",
            confidence=max(mechanic.confidence, 91),
            builder_id=MECHANIC_LIBRARY["grow"]["builder_id"],
            evidence=list(dict.fromkeys([
                *mechanic.evidence,
                "detected size-growth concept",
            ])),
            alternatives=mechanic.alternatives,
        )

    duration = float(
        scene_spec.get("duration")
        or decomposition.get("duration")
        or 8.0
    )
    avatar_count = int(scene_spec.get("avatar_count") or 1)

    lighting = "bright_cartoon"
    if scene.value == "horror_corridor":
        lighting = "dark_horror"
    elif scene.value == "hospital":
        lighting = "clean_indoor"
    elif scene.value == "city":
        lighting = "daylight_city"

    required_assets: list[str] = []
    blocked_reasons: list[str] = []

    procedural = bool(
        MECHANIC_LIBRARY.get(mechanic.value, {}).get("procedural", False)
    )

    if mechanic.value == "game_specific_unknown":
        required_assets.append(
            "custom Roblox mechanic implementation"
        )
        blocked_reasons.append(
            "exact game-specific mechanic was detected"
        )

    if scene.value not in SCENE_LIBRARY:
        required_assets.append("custom scene template")

    generation_mode = (
        "PROCEDURAL"
        if procedural and not blocked_reasons
        else "CUSTOM_ASSET_REQUIRED"
    )

    builder_sequence = [
        scene.builder_id,
        mechanic.builder_id,
        camera.builder_id,
        *[
            choice.builder_id
            for choice in ui
            if choice.value != "none"
        ],
    ]

    all_confidences = [
        scene.confidence,
        mechanic.confidence,
        camera.confidence,
        *[choice.confidence for choice in ui],
    ]
    overall_confidence = int(
        round(sum(all_confidences) / max(1, len(all_confidences)))
    )

    plan = RobloxBrainPlan(
        source_name=source_name,
        scene=scene,
        mechanic=mechanic,
        camera=camera,
        ui=ui,
        duration=round(duration, 2),
        avatar_count=avatar_count,
        lighting=lighting,
        procedural=procedural,
        required_assets=required_assets,
        blocked_reasons=blocked_reasons,
        overall_confidence=overall_confidence,
        generation_mode=generation_mode,
        builder_sequence=builder_sequence,
        notes=[
            "Part 2 chooses reusable Roblox concepts.",
            "Part 3 will execute builder_sequence inside Studio.",
            "Generic narrated format alone never selects Animal Hospital.",
        ],
    )
    plan.save()
    return plan


def load_roblox_brain_plan(
    source_name: str,
) -> RobloxBrainPlan | None:
    path = OUTPUT_DIR / f"{_safe_name(source_name)}.roblox_brain.json"
    if not path.exists():
        return None

    data = json.loads(path.read_text(encoding="utf-8"))
    return RobloxBrainPlan(
        source_name=data["source_name"],
        scene=BrainChoice(**data["scene"]),
        mechanic=BrainChoice(**data["mechanic"]),
        camera=BrainChoice(**data["camera"]),
        ui=[BrainChoice(**item) for item in data.get("ui", [])],
        duration=float(data.get("duration") or 8),
        avatar_count=int(data.get("avatar_count") or 1),
        lighting=str(data.get("lighting") or "bright_cartoon"),
        procedural=bool(data.get("procedural")),
        required_assets=list(data.get("required_assets") or []),
        blocked_reasons=list(data.get("blocked_reasons") or []),
        overall_confidence=int(data.get("overall_confidence") or 0),
        generation_mode=str(data.get("generation_mode") or ""),
        builder_sequence=list(data.get("builder_sequence") or []),
        notes=list(data.get("notes") or []),
    )
