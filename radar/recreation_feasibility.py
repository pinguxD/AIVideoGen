from __future__ import annotations
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from .full_video_analyzer import BASE
from .scene_decomposer import Decomposition

OUT = BASE / "outputs" / "recreation_intelligence"

@dataclass
class Component:
    component: str
    score: int
    method: str
    evidence: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

@dataclass
class Feasibility:
    source_file: str
    verdict: str
    overall_score: int
    recommended_engine: str
    prerecorded_footage_required: bool
    components: list[Component]
    exact_inputs_needed: list[str]
    safe_to_generate_scene_spec: bool
    warnings: list[str]
    def save(self):
        OUT.mkdir(parents=True, exist_ok=True)
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in Path(self.source_file).stem).strip("_") or "reference"
        path = OUT / f"{safe}.feasibility.json"
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        return path

def component(name, score, method, evidence, missing=None):
    return Component(name, max(0, min(100, int(score))), method, evidence, missing or [])

def assess(decomposition: Decomposition, plan: dict[str, Any] | None = None) -> Feasibility:
    plan = plan or {}
    notes = str((plan.get("human_labels") or {}).get("notes") or "").lower()
    scene_count, transition_count = len(decomposition.scenes), len(decomposition.transitions)
    items = [
        component("environment_and_scene", 88 if scene_count <= 3 else 68 if scene_count <= 7 else 42,
                  "roblox_studio_procedural" if scene_count <= 3 else "roblox_studio_templates",
                  [f"{scene_count} detected scenes"]),
        component("avatar_and_character", 48 if "exact avatar" in notes else 86,
                  "roblox_r15_generator",
                  ["generic R15 avatars are procedural", "exact identity recognition is not implemented"],
                  ["exact avatar/model asset"] if "exact avatar" in notes else []),
        component("camera", 84 if float(decomposition.editing_summary.get("average_motion") or 0) <= .30 else 68,
                  "scripted_camera_path", ["camera motion can be reconstructed from scene timing"]),
        component("gameplay_mechanic", 35 if any(x in notes for x in ("game-specific", "multiplayer", "rare event", "exact mechanic")) else 78,
                  "roblox_lua_procedural_mechanic",
                  ["movement, scaling, spawning and transformations are scriptable"],
                  ["game-specific mechanic implementation or permitted footage"]
                  if any(x in notes for x in ("game-specific", "multiplayer", "rare event", "exact mechanic")) else []),
        component("ui_and_overlays", 76, "roblox_gui_plus_post_renderer",
                  ["sliders, arrows, circles and captions can be generated"]),
        component("editing_and_transitions", 92 if transition_count <= 12 else 78,
                  "ffmpeg_or_moviepy_timeline", [f"{transition_count} transitions detected"]),
    ]
    total_sounds = len(decomposition.sound_effects)
    known_sounds = sum(x.family != "unknown_effect" for x in decomposition.sound_effects)
    items.append(component(
        "sound_design", 82 if total_sounds == 0 else int(55 + 35 * known_sounds / max(1, total_sounds)),
        "licensed_sound_library", [f"{total_sounds} effects, {known_sounds} classified"],
        [f"identify or approve {total_sounds - known_sounds} unknown sound effects"] if known_sounds < total_sounds else []
    ))
    voice = bool(decomposition.audio_layers.get("probable_voiceover"))
    items.append(component("voiceover", 95 if voice else 90, "tts_or_user_voice",
                           ["voice timing is generatable"], ["voice or TTS choice"] if voice else []))
    weights = {"environment_and_scene": .18, "avatar_and_character": .13, "camera": .10,
               "gameplay_mechanic": .22, "ui_and_overlays": .10,
               "editing_and_transitions": .10, "sound_design": .10, "voiceover": .07}
    overall = round(sum(item.score * weights[item.component] for item in items))
    missing = list(dict.fromkeys(value for item in items for value in item.missing))
    lowest = min(item.score for item in items)
    if overall >= 82 and lowest >= 60:
        verdict, engine, prerecorded = "SELF_GENERATE", "roblox_studio_procedural", False
    elif overall >= 68 and lowest >= 42:
        verdict, engine, prerecorded = "SELF_GENERATE_WITH_ASSETS", "roblox_studio_hybrid", False
    elif overall >= 52:
        verdict, engine, prerecorded = "NEEDS_USER_INPUT", "hybrid_existing_assets", any("footage" in x.lower() for x in missing)
    else:
        verdict, engine, prerecorded = "CANNOT_RECREATE_RELIABLY", "manual_or_permitted_footage", True
    result = Feasibility(
        decomposition.source_file, verdict, int(overall), engine, prerecorded,
        items, missing, verdict in {"SELF_GENERATE", "SELF_GENERATE_WITH_ASSETS"},
        ["v1 does not identify exact Roblox games or maps from pixels.",
         "A high score means the structure is generatable, not copied asset-for-asset."]
    )
    result.save()
    return result
