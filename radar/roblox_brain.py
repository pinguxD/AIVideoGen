from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import mean, median
from typing import Any

from .analysis_review import load_review_bundle
from .full_video_analyzer import BASE

OUTPUT_DIR = BASE / "outputs" / "roblox_brain"
RECREATION_DIR = BASE / "outputs" / "recreation_intelligence"

SCENE_LIBRARY: dict[str, dict[str, Any]] = {
    "simple_platform": {
        "keywords": ["platform", "baseplate"],
        "builder_id": "scene.simple_platform.v1",
    },
    "simple_obby": {
        "keywords": ["obby", "obstacle", "parkour", "stage"],
        "builder_id": "scene.simple_obby.v1",
    },
    "hospital": {
        "keywords": ["hospital", "doctor", "nurse", "patient", "clinic"],
        "builder_id": "scene.hospital.v1",
    },
    "city": {
        "keywords": ["city", "street", "road", "town"],
        "builder_id": "scene.city.v1",
    },
    "horror_corridor": {
        "keywords": ["horror", "dark hallway", "corridor", "monster", "scary"],
        "builder_id": "scene.horror_corridor.v1",
    },
    "character_showcase": {
        "keywords": ["avatar", "character", "head", "body", "size", "scale"],
        "builder_id": "scene.character_showcase.v1",
    },
}

ACTION_LIBRARY: dict[str, dict[str, Any]] = {
    "grow": {
        "keywords": ["grow", "bigger", "giant", "increase size", "oversized"],
        "builder_id": "mechanic.grow.v1",
        "priority": 95,
        "kind": "event",
    },
    "shrink": {
        "keywords": ["shrink", "smaller", "tiny", "decrease size"],
        "builder_id": "mechanic.shrink.v1",
        "priority": 92,
        "kind": "event",
    },
    "walk": {
        "keywords": ["walk", "walking", "move forward", "run", "moving"],
        "builder_id": "mechanic.walk.v1",
        "priority": 55,
        "kind": "state",
    },
    "jump": {
        "keywords": ["jump", "jumping", "leap", "airborne"],
        "builder_id": "mechanic.jump.v1",
        "priority": 60,
        "kind": "event",
    },
    "turn": {
        "keywords": ["turn", "rotate avatar", "looks around"],
        "builder_id": "mechanic.turn.v1",
        "priority": 45,
        "kind": "event",
    },
    "idle": {
        "keywords": ["idle", "standing", "wait"],
        "builder_id": "mechanic.idle.v1",
        "priority": 20,
        "kind": "state",
    },
    "chase": {
        "keywords": ["chase", "chasing", "follow player", "monster follows"],
        "builder_id": "mechanic.chase.v1",
        "priority": 85,
        "kind": "state",
    },
    "press_button": {
        "keywords": ["button", "press", "click", "switch"],
        "builder_id": "mechanic.press_button.v1",
        "priority": 75,
        "kind": "event",
    },
    "spawn_object": {
        "keywords": ["spawn", "summon", "create object"],
        "builder_id": "mechanic.spawn_object.v1",
        "priority": 80,
        "kind": "event",
    },
    "reveal_object": {
        "keywords": ["reveal", "secret", "hidden", "show object"],
        "builder_id": "mechanic.reveal_object.v1",
        "priority": 78,
        "kind": "event",
    },
    "game_specific_unknown": {
        "keywords": ["game-specific", "exact mechanic", "live server", "rare event"],
        "builder_id": "mechanic.custom_required",
        "priority": 100,
        "kind": "event",
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
        "keywords": ["close-up", "closeup", "head focus"],
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
    "size_slider": {
        "keywords": ["size slider", "slider", "scale ui", "size:"],
        "builder_id": "ui.size_slider.v1",
    },
    "counter": {
        "keywords": ["counter", "count", "number display", "size:"],
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
class TimelineAction:
    start: float
    end: float
    action: str
    role: str
    action_kind: str
    confidence: int
    builder_id: str
    properties: dict[str, Any] = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)


@dataclass
class TimelineEvent:
    time: float
    event_type: str
    confidence: int
    builder_id: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class RobloxBrainPlan:
    source_name: str
    scene: BrainChoice
    core_mechanic: BrainChoice
    supporting_actions: list[BrainChoice]
    state_actions: list[BrainChoice]
    event_actions: list[BrainChoice]
    action_timeline: list[TimelineAction]
    camera: BrainChoice
    camera_timeline: list[TimelineEvent]
    camera_pattern: dict[str, Any]
    ui: list[BrainChoice]
    editing_timeline: list[TimelineEvent]
    editing_pattern: dict[str, Any]
    audio_timeline: list[TimelineEvent]
    audio_pattern: dict[str, Any]
    character_state: dict[str, Any]
    environment_graph: dict[str, Any]
    understanding: dict[str, Any]
    execution_plan: list[dict[str, Any]]
    video_dna: dict[str, Any]
    why_it_works: list[dict[str, Any]]
    recreation_difficulty: dict[str, Any]
    execution_loops: list[dict[str, Any]]
    retention_blueprint: dict[str, Any]
    recreation_quality: dict[str, Any]
    build_instructions: list[dict[str, Any]]
    duration: float
    avatar_count: int
    lighting: str
    procedural: bool
    required_assets: list[str]
    blocked_reasons: list[str]
    overall_confidence: int
    generation_mode: str
    complexity: str
    builder_sequence: list[str]
    notes: list[str] = field(default_factory=list)

    @property
    def mechanic(self) -> BrainChoice:
        # Backwards-compatible alias for existing UI/plugin code.
        return self.core_mechanic

    def save(self) -> Path:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUTPUT_DIR / f"{_safe_name(self.source_name)}.roblox_brain.json"
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
    return (
        json.loads(candidates[0].read_text(encoding="utf-8"))
        if candidates
        else {}
    )


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
        *(str(value) for value in correction.values()),
        json.dumps(plan, ensure_ascii=False),
        json.dumps(analysis, ensure_ascii=False),
        json.dumps(scene_spec, ensure_ascii=False),
        json.dumps(decomposition.get("visual_events") or [], ensure_ascii=False),
    ]
    return " ".join(fragments).lower(), scene_spec, decomposition


def _score_choice(
    context: str,
    library: dict[str, dict[str, Any]],
    default_value: str,
) -> BrainChoice:
    scored: list[tuple[int, str, list[str]]] = []
    for value, metadata in library.items():
        evidence = [
            f"matched keyword: {keyword}"
            for keyword in metadata.get("keywords", [])
            if keyword.lower() in context
        ]
        score = len(evidence) * 22 + (8 if value == default_value else 0)
        scored.append((score, value, evidence))

    scored.sort(reverse=True)
    score, value, evidence = scored[0]
    if score <= 8:
        value = default_value
        score = 42
        evidence = ["safe procedural fallback"]

    return BrainChoice(
        value=value,
        confidence=max(35, min(96, 48 + score)),
        builder_id=str(library[value]["builder_id"]),
        evidence=evidence,
        alternatives=[
            candidate
            for candidate_score, candidate, _ in scored[1:4]
            if candidate_score > 8
        ],
    )


def _detect_scale(scene_spec: dict[str, Any], context: str) -> float | None:
    avatars = scene_spec.get("avatars") or []
    for avatar in avatars:
        scale = avatar.get("scale") or {}
        for key in ("head", "height", "width"):
            try:
                value = float(scale.get(key) or 1)
            except (TypeError, ValueError):
                continue
            if value > 1.15:
                return value

    if "679%" in context or "6.79" in context:
        return 6.79
    return None


def _detect_actions(
    context: str,
    scene_spec: dict[str, Any],
    decomposition: dict[str, Any],
    duration: float,
) -> tuple[BrainChoice, list[BrainChoice], list[BrainChoice], list[BrainChoice], list[TimelineAction]]:
    matches: list[BrainChoice] = []

    for action, metadata in ACTION_LIBRARY.items():
        evidence = [
            f"matched keyword: {keyword}"
            for keyword in metadata["keywords"]
            if keyword.lower() in context
        ]
        if evidence:
            matches.append(
                BrainChoice(
                    value=action,
                    confidence=min(96, 62 + len(evidence) * 12),
                    builder_id=metadata["builder_id"],
                    evidence=evidence,
                )
            )

    scale_value = _detect_scale(scene_spec, context)
    if scale_value is not None and not any(item.value == "grow" for item in matches):
        matches.append(
            BrainChoice(
                value="grow",
                confidence=94,
                builder_id=ACTION_LIBRARY["grow"]["builder_id"],
                evidence=[f"avatar scale exceeds normal size: {scale_value:g}x"],
            )
        )

    # Scene motion means some locomotion is likely even when text did not say so.
    average_motion = float(
        (decomposition.get("editing_summary") or {}).get("average_motion")
        or 0
    )
    if average_motion >= 0.03 and not any(
        item.value in {"walk", "jump", "turn"} for item in matches
    ):
        matches.append(
            BrainChoice(
                value="walk",
                confidence=64,
                builder_id=ACTION_LIBRARY["walk"]["builder_id"],
                evidence=["continuous scene motion suggests locomotion"],
            )
        )

    # In avatar showcase/obby clips, short vertical/whip events are a weak jump clue.
    transitions = decomposition.get("transitions") or []
    vertical_events = [
        item for item in transitions
        if "vertical" in str(item.get("kind") or item.get("transition_type") or "")
    ]
    if vertical_events and not any(item.value == "jump" for item in matches):
        matches.append(
            BrainChoice(
                value="jump",
                confidence=58,
                builder_id=ACTION_LIBRARY["jump"]["builder_id"],
                evidence=["vertical motion event may correspond to a jump"],
            )
        )

    if not matches:
        matches.append(
            BrainChoice(
                value="idle",
                confidence=45,
                builder_id=ACTION_LIBRARY["idle"]["builder_id"],
                evidence=["no stronger action evidence"],
            )
        )

    # Core mechanic is not simply the highest keyword count. Transformations and
    # interactions outrank background locomotion.
    matches.sort(
        key=lambda item: (
            ACTION_LIBRARY[item.value]["priority"],
            item.confidence,
        ),
        reverse=True,
    )
    core = matches[0]
    supporting = matches[1:]
    state_actions = [
        item for item in matches
        if ACTION_LIBRARY[item.value].get("kind") == "state"
    ]
    event_actions = [
        item for item in matches
        if ACTION_LIBRARY[item.value].get("kind") == "event"
    ]

    # Create a deterministic first-pass timeline. It uses scene boundaries when
    # available and can later be replaced by learned action recognition.
    scenes = decomposition.get("scenes") or []
    boundaries = [0.0]
    for scene in scenes:
        try:
            boundaries.append(float(scene.get("end") or 0))
        except (TypeError, ValueError):
            continue
    boundaries = sorted(
        set(round(value, 3) for value in boundaries if 0 <= value <= duration)
    )
    if not boundaries or boundaries[-1] < duration:
        boundaries.append(duration)

    ordered = [*supporting, core]
    # Put locomotion before/around the main mechanic when possible.
    ordered.sort(
        key=lambda item: (
            0 if item.value in {"walk", "idle", "turn"} else
            1 if item.value == core.value else
            2
        )
    )
    if core not in ordered:
        ordered.append(core)

    timeline: list[TimelineAction] = []
    segment_count = max(len(ordered), 1)
    for index, choice in enumerate(ordered):
        if len(boundaries) >= segment_count + 1:
            start = boundaries[min(index, len(boundaries) - 2)]
            end = boundaries[min(index + 1, len(boundaries) - 1)]
        else:
            start = duration * index / segment_count
            end = duration * (index + 1) / segment_count

        properties: dict[str, Any] = {}
        if choice.value == "grow" and scale_value is not None:
            properties = {"target_scale": scale_value}
        elif choice.value == "jump":
            properties = {"jump_power": 50}
        elif choice.value == "walk":
            properties = {"walk_speed": 16}

        timeline.append(
            TimelineAction(
                start=round(start, 3),
                end=round(max(end, start + 0.25), 3),
                action=choice.value,
                role="core" if choice.value == core.value else "supporting",
                action_kind=str(ACTION_LIBRARY[choice.value].get("kind") or "event"),
                confidence=choice.confidence,
                builder_id=choice.builder_id,
                properties=properties,
                evidence=choice.evidence,
            )
        )

    return core, supporting, state_actions, event_actions, timeline


def _infer_ui(
    context: str,
    scene_spec: dict[str, Any],
) -> list[BrainChoice]:
    choices: dict[str, BrainChoice] = {}

    for value, metadata in UI_LIBRARY.items():
        evidence = [
            f"matched keyword: {keyword}"
            for keyword in metadata["keywords"]
            if keyword.lower() in context
        ]
        if evidence:
            choices[value] = BrainChoice(
                value=value,
                confidence=min(96, 62 + len(evidence) * 12),
                builder_id=metadata["builder_id"],
                evidence=evidence,
            )

    for item in scene_spec.get("gui") or []:
        item_type = str(item.get("type") or "").lower()
        if item_type == "slider":
            choices["size_slider"] = BrainChoice(
                value="size_slider",
                confidence=96,
                builder_id=UI_LIBRARY["size_slider"]["builder_id"],
                evidence=["scene specification contains a slider"],
            )
            choices.setdefault(
                "counter",
                BrainChoice(
                    value="counter",
                    confidence=82,
                    builder_id=UI_LIBRARY["counter"]["builder_id"],
                    evidence=["slider label/value requires a visible counter"],
                ),
            )

    return list(choices.values()) or [
        BrainChoice(
            value="none",
            confidence=70,
            builder_id="ui.none.v1",
            evidence=["no UI evidence detected"],
        )
    ]


def _camera_events(
    decomposition: dict[str, Any],
    default_camera: BrainChoice,
) -> list[TimelineEvent]:
    events = [
        TimelineEvent(
            time=0.0,
            event_type=default_camera.value,
            confidence=default_camera.confidence,
            builder_id=default_camera.builder_id,
        )
    ]

    for item in decomposition.get("transitions") or []:
        kind = str(
            item.get("kind")
            or item.get("transition_type")
            or ""
        )
        try:
            time_value = float(item.get("time") or 0)
        except (TypeError, ValueError):
            continue

        if "zoom" in kind:
            events.append(
                TimelineEvent(
                    time=round(time_value, 3),
                    event_type="zoom_pulse",
                    confidence=int(item.get("confidence") or 70),
                    builder_id="camera.zoom_pulse.v1",
                )
            )
        elif "whip_pan" in kind:
            events.append(
                TimelineEvent(
                    time=round(time_value, 3),
                    event_type=kind,
                    confidence=int(item.get("confidence") or 70),
                    builder_id="camera.whip_pan.v1",
                )
            )

    return _dedupe_events(events)


def _editing_events(decomposition: dict[str, Any]) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []
    camera_only_tokens = (
        "whip_pan",
        "camera_pan",
        "camera_orbit",
        "camera_push",
        "zoom_pulse",
    )
    for item in decomposition.get("transitions") or []:
        kind = str(
            item.get("kind")
            or item.get("transition_type")
            or "transition"
        )
        # Camera movement belongs to Camera Style, not Editing Style.
        if any(token in kind for token in camera_only_tokens):
            continue
        events.append(
            TimelineEvent(
                time=round(float(item.get("time") or 0), 3),
                event_type=kind,
                confidence=int(item.get("confidence") or 60),
                builder_id=f"edit.{kind}.v1",
            )
        )

    for item in decomposition.get("visual_events") or []:
        events.append(
            TimelineEvent(
                time=round(float(item.get("start") or 0), 3),
                event_type=str(item.get("event_type") or "visual_overlay"),
                confidence=int(item.get("confidence") or 60),
                builder_id="edit.visual_overlay.v1",
                properties={
                    "end": float(item.get("end") or item.get("start") or 0)
                },
            )
        )
    return _dedupe_events(sorted(events, key=lambda item: item.time))


def _audio_events(decomposition: dict[str, Any]) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []
    for item in decomposition.get("sound_effects") or []:
        family = str(
            item.get("family")
            or item.get("effect_type")
            or "unknown_effect"
        )
        events.append(
            TimelineEvent(
                time=round(float(item.get("start") or 0), 3),
                event_type=family,
                confidence=int(item.get("confidence") or 50),
                builder_id=f"audio.{family}.v1",
                properties={
                    "end": float(item.get("end") or item.get("start") or 0)
                },
            )
        )
    return events



def _dedupe_events(
    events: list[TimelineEvent],
    window: float = 0.30,
) -> list[TimelineEvent]:
    output: list[TimelineEvent] = []
    for event in sorted(events, key=lambda item: item.time):
        if (
            output
            and output[-1].event_type == event.event_type
            and event.time - output[-1].time <= window
        ):
            if event.confidence > output[-1].confidence:
                output[-1] = event
            continue
        output.append(event)
    return output


def _pattern_summary(
    base: str,
    events: list[TimelineEvent],
    duration: float,
) -> dict[str, Any]:
    relevant = [event for event in events if event.event_type != base]
    if not relevant:
        return {
            "base": base,
            "dominant_pattern": "none",
            "occurrences": 0,
            "average_interval": None,
            "median_interval": None,
            "exceptions": [],
            "pacing": "slow",
        }

    counts: dict[str, int] = {}
    for event in relevant:
        counts[event.event_type] = counts.get(event.event_type, 0) + 1

    dominant = max(counts, key=counts.get)
    dominant_events = [
        event for event in relevant
        if event.event_type == dominant
    ]
    intervals = [
        dominant_events[index].time - dominant_events[index - 1].time
        for index in range(1, len(dominant_events))
        if dominant_events[index].time > dominant_events[index - 1].time
    ]
    event_rate = len(relevant) / max(duration, 0.1)
    pacing = (
        "very_fast" if event_rate >= 1.0 else
        "fast" if event_rate >= 0.55 else
        "medium" if event_rate >= 0.25 else
        "slow"
    )
    return {
        "base": base,
        "dominant_pattern": dominant,
        "occurrences": len(dominant_events),
        "average_interval": round(mean(intervals), 3) if intervals else None,
        "median_interval": round(median(intervals), 3) if intervals else None,
        "exceptions": [
            {
                "time": event.time,
                "event_type": event.event_type,
                "confidence": event.confidence,
            }
            for event in relevant
            if event.event_type != dominant
        ][:12],
        "pacing": pacing,
    }


def _character_state(
    scene_spec: dict[str, Any],
    state_actions: list[BrainChoice],
    scale_value: float | None,
) -> dict[str, Any]:
    avatar = (scene_spec.get("avatars") or [{}])[0]
    movement = state_actions[0].value if state_actions else "idle"
    return {
        "rig": str(avatar.get("rig") or "R15"),
        "scale": round(float(scale_value or 1.0), 3),
        "health": 100,
        "facing": "forward",
        "movement_state": movement,
        "animation": "WalkCycle01" if movement == "walk" else "IdleCycle01",
        "appearance": str(
            avatar.get("appearance") or "generic_original_avatar"
        ),
    }


def _environment_graph(scene_value: str, lighting: str) -> dict[str, Any]:
    nodes = {
        "simple_platform": ["Baseplate", "Spawn", "Skybox", "Lighting"],
        "simple_obby": ["Baseplate", "Obby", "Spawn", "Finish", "Skybox", "Lighting"],
        "hospital": ["Floor", "Walls", "Reception", "HospitalRoom", "Spawn", "Lighting"],
        "city": ["Road", "Sidewalk", "Buildings", "Spawn", "Skybox", "Lighting"],
        "horror_corridor": ["Corridor", "Doors", "Spawn", "DarkLighting"],
        "character_showcase": ["Baseplate", "ShowcaseArea", "Spawn", "Skybox", "Lighting"],
    }.get(scene_value, ["Baseplate", "Spawn", "Skybox", "Lighting"])
    return {
        "scene_type": scene_value,
        "nodes": nodes,
        "npc_count": 0,
        "enemy_count": 0,
        "has_buildings": scene_value in {"hospital", "city"},
        "has_spawn": True,
        "skybox": "default",
        "lighting": lighting,
    }


def _execution_plan(
    scene: BrainChoice,
    character_state: dict[str, Any],
    environment_graph: dict[str, Any],
    action_timeline: list[TimelineAction],
    ui: list[BrainChoice],
    camera_timeline: list[TimelineEvent],
    editing_timeline: list[TimelineEvent],
    audio_timeline: list[TimelineEvent],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = [
        {
            "order": 1,
            "phase": "environment",
            "command": "build_environment",
            "builder_id": scene.builder_id,
            "properties": environment_graph,
        },
        {
            "order": 2,
            "phase": "character",
            "command": "spawn_character",
            "builder_id": "character.spawn_r15.v1",
            "properties": character_state,
        },
    ]
    order = 3
    for action in action_timeline:
        items.append({
            "order": order,
            "phase": "gameplay",
            "command": action.action,
            "builder_id": action.builder_id,
            "start": action.start,
            "end": action.end,
            "properties": action.properties,
        })
        order += 1
    for choice in ui:
        if choice.value != "none":
            items.append({
                "order": order,
                "phase": "ui",
                "command": choice.value,
                "builder_id": choice.builder_id,
                "properties": {},
            })
            order += 1
    for phase, events in (
        ("camera", camera_timeline),
        ("editing", editing_timeline),
        ("audio", audio_timeline),
    ):
        for event in events:
            items.append({
                "order": order,
                "phase": phase,
                "command": event.event_type,
                "builder_id": event.builder_id,
                "time": event.time,
                "properties": event.properties,
            })
            order += 1
    return items


def _complexity(
    action_count: int,
    ui_count: int,
    event_count: int,
    procedural: bool,
) -> str:
    if not procedural:
        return "custom"
    score = action_count + ui_count + event_count / 8
    return "low" if score <= 4 else "medium" if score <= 8 else "high"



def _why_it_works(core, state_actions, ui, camera_pattern, editing_pattern, duration):
    reasons = []
    if state_actions:
        reasons.append({
            "reason": "constant_motion",
            "label": "Constant motion",
            "confidence": max(item.confidence for item in state_actions),
            "explanation": "The avatar remains active instead of standing still, which keeps the frame visually alive.",
        })
    if core.value in {"grow", "shrink", "reveal_object", "spawn_object"}:
        reasons.append({
            "reason": "clear_progression",
            "label": "Clear visual progression",
            "confidence": core.confidence,
            "explanation": f"The central mechanic ({core.value}) creates an obvious before-to-after change.",
        })
    visible_ui = [item for item in ui if item.value != "none"]
    if visible_ui:
        reasons.append({
            "reason": "ui_reinforcement",
            "label": "UI reinforces the mechanic",
            "confidence": int(round(sum(x.confidence for x in visible_ui) / len(visible_ui))),
            "explanation": "Counters, sliders, arrows, or highlights make the main gameplay change easier to understand instantly.",
        })
    if int(camera_pattern.get("occurrences") or 0) >= 2:
        interval = camera_pattern.get("average_interval")
        reasons.append({
            "reason": "camera_attention_resets",
            "label": "Frequent camera attention resets",
            "confidence": 82,
            "explanation": "Repeated camera movement prevents the shot from feeling static." + (f" The dominant camera event repeats about every {interval}s." if interval is not None else ""),
        })
    if str(editing_pattern.get("pacing") or "unknown") in {"fast", "very_fast"}:
        reasons.append({
            "reason": "fast_pacing",
            "label": "Fast pacing",
            "confidence": 86,
            "explanation": "Frequent visual changes create repeated attention resets.",
        })
    event_rate = int(editing_pattern.get("occurrences") or 0) / max(float(duration), 0.1)
    if event_rate >= 0.65:
        reasons.append({
            "reason": "frequent_visual_change",
            "label": "New visual information appears frequently",
            "confidence": 84,
            "explanation": "The viewer receives a meaningful visual change roughly every one to two seconds or faster.",
        })
    if not reasons:
        reasons.append({
            "reason": "simple_readability",
            "label": "Simple and readable concept",
            "confidence": 60,
            "explanation": "The video uses a straightforward gameplay idea that is easy to understand without explanation.",
        })
    return reasons


def _recreation_difficulty(procedural, complexity, action_count, ui_count, camera_event_count, editing_event_count, required_assets):
    score = action_count * 7 + ui_count * 5 + min(camera_event_count, 12) * 2 + min(editing_event_count, 18)
    score += 35 if not procedural else 0
    score += len(required_assets) * 12
    score += 18 if complexity == "high" else 8 if complexity == "medium" else 0
    score = max(0, min(100, int(round(score))))
    label = "Easy" if score <= 24 else "Medium" if score <= 49 else "Hard" if score <= 74 else "Expert"
    reasons = []
    if action_count >= 4: reasons.append("multiple gameplay actions")
    if ui_count >= 3: reasons.append("several UI elements")
    if camera_event_count >= 8: reasons.append("dense camera choreography")
    if editing_event_count >= 12: reasons.append("fast editing timeline")
    if not procedural: reasons.append("custom mechanic or asset work")
    if required_assets: reasons.append("external assets are required")
    if not reasons: reasons.append("mostly procedural and reusable")
    return {"label": label, "score": score, "reasons": reasons, "fully_procedural": procedural and not required_assets}


def _build_execution_loops(action_timeline, camera_pattern, editing_pattern, audio_pattern, ui):
    loops = []
    states = [item for item in action_timeline if item.action_kind == "state"]
    events = [item for item in action_timeline if item.action_kind == "event"]
    if states:
        loops.append({"phase": "gameplay", "name": "base_state_loop", "command": states[0].action, "builder_id": states[0].builder_id, "start": states[0].start, "end": states[-1].end})
    for item in events:
        loops.append({"phase": "gameplay", "name": f"{item.action}_event", "command": item.action, "builder_id": item.builder_id, "start": item.start, "end": item.end, "properties": item.properties})
    if int(camera_pattern.get("occurrences") or 0) > 1:
        loops.append({"phase": "camera", "name": "camera_pattern_loop", "command": camera_pattern.get("dominant_pattern") or "none", "builder_id": "camera.pattern_loop.v1", "interval": camera_pattern.get("average_interval"), "occurrences": camera_pattern.get("occurrences"), "exceptions": camera_pattern.get("exceptions") or []})
    if int(editing_pattern.get("occurrences") or 0) > 1:
        loops.append({"phase": "editing", "name": "editing_pattern_loop", "command": editing_pattern.get("dominant_pattern") or "none", "builder_id": "edit.pattern_loop.v1", "interval": editing_pattern.get("average_interval"), "occurrences": editing_pattern.get("occurrences"), "pacing": editing_pattern.get("pacing"), "exceptions": editing_pattern.get("exceptions") or []})
    if int(audio_pattern.get("occurrences") or 0) > 1:
        loops.append({"phase": "audio", "name": "audio_pattern_loop", "command": audio_pattern.get("dominant_pattern") or "none", "builder_id": "audio.pattern_loop.v1", "interval": audio_pattern.get("average_interval"), "occurrences": audio_pattern.get("occurrences"), "exceptions": audio_pattern.get("exceptions") or []})
    visible_ui = [item for item in ui if item.value != "none"]
    if visible_ui:
        loops.append({"phase": "ui", "name": "persistent_ui", "command": "show_ui", "builder_id": "ui.persistent_group.v1", "elements": [item.value for item in visible_ui]})
    return loops


def _clamp_score(value: float) -> int:
    return max(0, min(100, int(round(value))))


def _retention_blueprint(
    core: BrainChoice,
    state_actions: list[BrainChoice],
    ui: list[BrainChoice],
    camera_pattern: dict[str, Any],
    editing_pattern: dict[str, Any],
    action_timeline: list[TimelineAction],
    duration: float,
) -> dict[str, Any]:
    visible_ui = [item for item in ui if item.value != "none"]
    transformation = core.value in {
        "grow", "shrink", "reveal_object", "spawn_object"
    }
    camera_rate = int(camera_pattern.get("occurrences") or 0) / max(duration, 0.1)
    editing_rate = int(editing_pattern.get("occurrences") or 0) / max(duration, 0.1)

    scores = {
        "hook": 72 + (10 if transformation else 0) + (6 if visible_ui else 0),
        "progression": 58 + (30 if transformation else 0) + min(12, len(action_timeline) * 3),
        "visual_novelty": 55 + min(25, int((camera_rate + editing_rate) * 18)) + (8 if visible_ui else 0),
        "constant_motion": 42 + (38 if state_actions else 0) + min(15, int(camera_rate * 12)),
        "clarity": 62 + (18 if visible_ui else 0) + (10 if transformation else 0),
        "reward": 55 + (28 if transformation else 0),
        "loopability": 58 + (12 if state_actions else 0) + (8 if core.value in {"grow", "walk", "chase"} else 0),
        "pacing": 50 + min(40, int((camera_rate + editing_rate) * 22)),
    }
    scores = {key: _clamp_score(value) for key, value in scores.items()}
    overall = _clamp_score(sum(scores.values()) / len(scores))

    drivers = []
    if transformation:
        drivers.append("clear before-to-after progression")
    if state_actions:
        drivers.append("continuous character motion")
    if visible_ui:
        drivers.append("UI makes the mechanic immediately readable")
    if camera_rate >= 0.45:
        drivers.append("frequent camera attention resets")
    if editing_rate >= 0.35:
        drivers.append("fast visual pacing")
    if not drivers:
        drivers.append("simple concept that is easy to understand")

    weakest = min(scores, key=scores.get)
    strongest = max(scores, key=scores.get)
    return {
        "overall_score": overall,
        "scores": scores,
        "strongest_driver": strongest,
        "weakest_driver": weakest,
        "drivers": drivers,
        "summary": (
            f"Retention is mainly driven by {strongest.replace('_', ' ')}; "
            f"the weakest area is {weakest.replace('_', ' ')}."
        ),
    }


def _recreation_quality(
    scene: BrainChoice,
    core: BrainChoice,
    camera: BrainChoice,
    ui: list[BrainChoice],
    audio_pattern: dict[str, Any],
    procedural: bool,
    required_assets: list[str],
) -> dict[str, Any]:
    visible_ui = [item for item in ui if item.value != "none"]
    audio_known = str(audio_pattern.get("dominant_pattern") or "none") not in {
        "none", "unknown_effect"
    }
    components = {
        "scene_understanding": scene.confidence,
        "gameplay_understanding": core.confidence,
        "camera_understanding": camera.confidence,
        "ui_understanding": (
            int(round(sum(item.confidence for item in visible_ui) / len(visible_ui)))
            if visible_ui else 70
        ),
        "audio_understanding": 82 if audio_known else 48,
        "procedural_feasibility": 96 if procedural and not required_assets else 58,
    }
    weights = {
        "scene_understanding": 0.18,
        "gameplay_understanding": 0.25,
        "camera_understanding": 0.15,
        "ui_understanding": 0.12,
        "audio_understanding": 0.10,
        "procedural_feasibility": 0.20,
    }
    overall = _clamp_score(sum(components[key] * weights[key] for key in components))
    label = (
        "Excellent" if overall >= 90 else
        "High" if overall >= 80 else
        "Moderate" if overall >= 65 else
        "Low"
    )
    limitations = []
    if not audio_known:
        limitations.append("exact sound effects are not fully identified")
    if required_assets:
        limitations.extend(required_assets)
    if core.confidence < 75:
        limitations.append("gameplay action confidence is limited")
    return {
        "score": overall,
        "label": label,
        "components": components,
        "limitations": limitations,
        "summary": f"Predicted recreation fidelity: {overall}% ({label}).",
    }


def _build_instruction_manual(
    environment_graph: dict[str, Any],
    character_state: dict[str, Any],
    action_timeline: list[TimelineAction],
    ui: list[BrainChoice],
    camera_pattern: dict[str, Any],
    editing_pattern: dict[str, Any],
    audio_pattern: dict[str, Any],
) -> list[dict[str, Any]]:
    instructions = [
        {
            "step": 1,
            "title": "Build environment",
            "instruction": (
                f"Create {environment_graph.get('scene_type', 'scene')} with: "
                + ", ".join(environment_graph.get("nodes") or [])
            ),
            "builder_id": f"scene.{environment_graph.get('scene_type', 'simple_platform')}.v1",
        },
        {
            "step": 2,
            "title": "Spawn character",
            "instruction": (
                f"Spawn {character_state.get('rig', 'R15')} avatar at "
                f"{character_state.get('scale', 1)}x scale, facing "
                f"{character_state.get('facing', 'forward')}."
            ),
            "builder_id": "character.spawn_r15.v1",
        },
    ]
    step = 3
    for action in action_timeline:
        detail = action.action
        if action.properties:
            detail += " with " + ", ".join(
                f"{key}={value}" for key, value in action.properties.items()
            )
        instructions.append({
            "step": step,
            "title": action.action.replace("_", " ").title(),
            "instruction": f"From {action.start}s to {action.end}s: {detail}.",
            "builder_id": action.builder_id,
        })
        step += 1

    visible_ui = [item for item in ui if item.value != "none"]
    if visible_ui:
        instructions.append({
            "step": step,
            "title": "Create UI",
            "instruction": "Add " + ", ".join(item.value for item in visible_ui) + ".",
            "builder_id": "ui.persistent_group.v1",
        })
        step += 1

    if int(camera_pattern.get("occurrences") or 0) > 0:
        instructions.append({
            "step": step,
            "title": "Apply camera rhythm",
            "instruction": (
                f"Use {camera_pattern.get('base')} and repeat "
                f"{camera_pattern.get('dominant_pattern')} about every "
                f"{camera_pattern.get('average_interval')}s."
            ),
            "builder_id": "camera.pattern_loop.v1",
        })
        step += 1

    if int(editing_pattern.get("occurrences") or 0) > 0:
        instructions.append({
            "step": step,
            "title": "Apply editing rhythm",
            "instruction": (
                f"Use {editing_pattern.get('dominant_pattern')} as the main edit, "
                f"with {editing_pattern.get('pacing')} pacing."
            ),
            "builder_id": "edit.pattern_loop.v1",
        })
        step += 1

    if int(audio_pattern.get("occurrences") or 0) > 0:
        instructions.append({
            "step": step,
            "title": "Apply audio cues",
            "instruction": (
                f"Use {audio_pattern.get('dominant_pattern')} as the dominant "
                f"sound family at the detected cue times."
            ),
            "builder_id": "audio.pattern_loop.v1",
        })
    return instructions

def build_roblox_brain_plan(source_name: str) -> RobloxBrainPlan:
    recreation = _load_recreation_bundle(source_name)
    context, scene_spec, decomposition = _collect_context(
        source_name,
        recreation,
    )

    scene = _score_choice(
        context,
        SCENE_LIBRARY,
        "simple_platform",
    )
    if any(token in context for token in ("avatar", "head", "body", "scale")):
        scene = BrainChoice(
            value="character_showcase",
            confidence=96,
            builder_id=SCENE_LIBRARY["character_showcase"]["builder_id"],
            evidence=[
                "avatar/body transformation context",
                *scene.evidence,
            ],
        )

    duration = float(
        scene_spec.get("duration")
        or decomposition.get("duration")
        or 8.0
    )
    core, supporting, state_actions, event_actions, action_timeline = _detect_actions(
        context,
        scene_spec,
        decomposition,
        duration,
    )

    camera = _score_choice(
        context,
        CAMERA_LIBRARY,
        "third_person_follow",
    )
    ui = _infer_ui(context, scene_spec)
    camera_timeline = _camera_events(decomposition, camera)
    editing_timeline = _editing_events(decomposition)
    audio_timeline = _audio_events(decomposition)

    lighting = {
        "horror_corridor": "dark_horror",
        "hospital": "clean_indoor",
        "city": "daylight_city",
    }.get(scene.value, "bright_cartoon")

    scale_value = _detect_scale(scene_spec, context)
    character_state = _character_state(
        scene_spec,
        state_actions,
        scale_value,
    )
    environment_graph = _environment_graph(scene.value, lighting)
    camera_pattern = _pattern_summary(
        camera.value,
        camera_timeline,
        duration,
    )
    editing_pattern = _pattern_summary(
        "timeline",
        editing_timeline,
        duration,
    )
    audio_pattern = _pattern_summary(
        "timeline",
        audio_timeline,
        duration,
    )

    procedural = core.value != "game_specific_unknown"
    required_assets = (
        []
        if procedural
        else ["custom Roblox mechanic implementation"]
    )
    blocked_reasons = (
        []
        if procedural
        else ["exact game-specific mechanic detected"]
    )

    execution_plan = _execution_plan(
        scene,
        character_state,
        environment_graph,
        action_timeline,
        ui,
        camera_timeline,
        editing_timeline,
        audio_timeline,
    )
    builder_sequence = list(dict.fromkeys(
        item["builder_id"]
        for item in execution_plan
        if item.get("builder_id")
    ))

    confidences = [
        scene.confidence,
        core.confidence,
        camera.confidence,
        *[item.confidence for item in supporting],
        *[item.confidence for item in ui],
    ]

    complexity = _complexity(
        len(action_timeline),
        len([item for item in ui if item.value != "none"]),
        len(camera_timeline) + len(editing_timeline) + len(audio_timeline),
        procedural,
    )
    understanding = {
        "scene": scene.value,
        "environment": environment_graph,
        "character": character_state,
        "core_mechanic": core.value,
        "continuous_states": [item.value for item in state_actions],
        "discrete_actions": [item.value for item in event_actions],
        "supporting_actions": [item.value for item in supporting],
        "ui": [item.value for item in ui if item.value != "none"],
        "camera_language": camera_pattern,
        "editing_language": editing_pattern,
        "audio_language": audio_pattern,
    }
    video_dna = {
        "gameplay": {
            "base_state": (
                state_actions[0].value if state_actions else "idle"
            ),
            "core_transformation": core.value,
            "supporting_actions": [item.value for item in supporting],
        },
        "camera": camera_pattern,
        "editing": editing_pattern,
        "audio": audio_pattern,
        "ui": [item.value for item in ui if item.value != "none"],
        "complexity": complexity,
        "generation_mode": (
            "PROCEDURAL" if procedural else "CUSTOM_ASSET_REQUIRED"
        ),
    }
    why_it_works = _why_it_works(core, state_actions, ui, camera_pattern, editing_pattern, duration)
    recreation_difficulty = _recreation_difficulty(
        procedural, complexity, len(action_timeline),
        len([item for item in ui if item.value != "none"]),
        len(camera_timeline), len(editing_timeline), required_assets,
    )
    execution_loops = _build_execution_loops(
        action_timeline, camera_pattern, editing_pattern, audio_pattern, ui,
    )
    video_dna["why_it_works"] = why_it_works
    video_dna["recreation_difficulty"] = recreation_difficulty
    retention_blueprint = _retention_blueprint(
        core, state_actions, ui, camera_pattern, editing_pattern,
        action_timeline, duration,
    )
    recreation_quality = _recreation_quality(
        scene, core, camera, ui, audio_pattern,
        procedural, required_assets,
    )
    build_instructions = _build_instruction_manual(
        environment_graph, character_state, action_timeline, ui,
        camera_pattern, editing_pattern, audio_pattern,
    )
    video_dna["retention_blueprint"] = retention_blueprint
    video_dna["recreation_quality"] = recreation_quality

    plan = RobloxBrainPlan(
        source_name=source_name,
        scene=scene,
        core_mechanic=core,
        supporting_actions=supporting,
        state_actions=state_actions,
        event_actions=event_actions,
        action_timeline=action_timeline,
        camera=camera,
        camera_timeline=camera_timeline,
        camera_pattern=camera_pattern,
        ui=ui,
        editing_timeline=editing_timeline,
        editing_pattern=editing_pattern,
        audio_timeline=audio_timeline,
        audio_pattern=audio_pattern,
        character_state=character_state,
        environment_graph=environment_graph,
        understanding=understanding,
        execution_plan=execution_plan,
        video_dna=video_dna,
        why_it_works=why_it_works,
        recreation_difficulty=recreation_difficulty,
        execution_loops=execution_loops,
        retention_blueprint=retention_blueprint,
        recreation_quality=recreation_quality,
        build_instructions=build_instructions,
        duration=round(duration, 3),
        avatar_count=int(scene_spec.get("avatar_count") or 1),
        lighting=lighting,
        procedural=procedural,
        required_assets=required_assets,
        blocked_reasons=blocked_reasons,
        overall_confidence=int(
            round(sum(confidences) / max(1, len(confidences)))
        ),
        generation_mode=(
            "PROCEDURAL"
            if procedural
            else "CUSTOM_ASSET_REQUIRED"
        ),
        complexity=complexity,
        builder_sequence=builder_sequence,
        notes=[
            "A video can contain multiple actions.",
            "Core mechanics outrank background locomotion.",
            "Action timing is currently heuristic and uses scene boundaries.",
            "Part 2A separates understanding from execution.",
            "Part 3 should read execution_loops first, then execution_plan for exceptions.",
            "Part 2A explains why the video works and estimates recreation difficulty.",
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

    required_fields = {
        "core_mechanic",
        "camera_pattern",
        "character_state",
        "environment_graph",
        "understanding",
        "execution_plan",
        "video_dna",
        "why_it_works",
        "recreation_difficulty",
        "execution_loops",
        "retention_blueprint",
        "recreation_quality",
        "build_instructions",
    }
    if not required_fields.issubset(data):
        return None

    return RobloxBrainPlan(
        source_name=data["source_name"],
        scene=BrainChoice(**data["scene"]),
        core_mechanic=BrainChoice(**data["core_mechanic"]),
        supporting_actions=[
            BrainChoice(**item)
            for item in data.get("supporting_actions", [])
        ],
        state_actions=[BrainChoice(**item) for item in data.get("state_actions", [])],
        event_actions=[BrainChoice(**item) for item in data.get("event_actions", [])],
        action_timeline=[
            TimelineAction(**item)
            for item in data.get("action_timeline", [])
        ],
        camera=BrainChoice(**data["camera"]),
        camera_timeline=[
            TimelineEvent(**item)
            for item in data.get("camera_timeline", [])
        ],
        camera_pattern=dict(data.get("camera_pattern") or {}),
        ui=[BrainChoice(**item) for item in data.get("ui", [])],
        editing_timeline=[
            TimelineEvent(**item)
            for item in data.get("editing_timeline", [])
        ],
        editing_pattern=dict(data.get("editing_pattern") or {}),
        audio_timeline=[
            TimelineEvent(**item)
            for item in data.get("audio_timeline", [])
        ],
        audio_pattern=dict(data.get("audio_pattern") or {}),
        character_state=dict(data.get("character_state") or {}),
        environment_graph=dict(data.get("environment_graph") or {}),
        understanding=dict(data.get("understanding") or {}),
        execution_plan=list(data.get("execution_plan") or []),
        video_dna=dict(data.get("video_dna") or {}),
        why_it_works=list(data.get("why_it_works") or []),
        recreation_difficulty=dict(data.get("recreation_difficulty") or {}),
        execution_loops=list(data.get("execution_loops") or []),
        retention_blueprint=dict(data.get("retention_blueprint") or {}),
        recreation_quality=dict(data.get("recreation_quality") or {}),
        build_instructions=list(data.get("build_instructions") or []),
        duration=float(data.get("duration") or 8),
        avatar_count=int(data.get("avatar_count") or 1),
        lighting=str(data.get("lighting") or "bright_cartoon"),
        procedural=bool(data.get("procedural")),
        required_assets=list(data.get("required_assets") or []),
        blocked_reasons=list(data.get("blocked_reasons") or []),
        overall_confidence=int(data.get("overall_confidence") or 0),
        generation_mode=str(data.get("generation_mode") or ""),
        complexity=str(data.get("complexity") or "unknown"),
        builder_sequence=list(data.get("builder_sequence") or []),
        notes=list(data.get("notes") or []),
    )
