from __future__ import annotations
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from .full_video_analyzer import BASE
from .scene_decomposer import Decomposition
from .recreation_feasibility import Feasibility

OUT = BASE / "outputs" / "roblox_scene_specs"

@dataclass
class SceneSpec:
    source_file: str
    version: str
    engine: str
    duration: float
    environment: dict[str, Any]
    avatars: list[dict[str, Any]]
    camera: dict[str, Any]
    gui: list[dict[str, Any]]
    timeline: list[dict[str, Any]]
    post_edit: dict[str, Any]
    unresolved: list[str]
    confidence: int
    def save(self):
        OUT.mkdir(parents=True, exist_ok=True)
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in Path(self.source_file).stem).strip("_") or "reference"
        path = OUT / f"{safe}.roblox_scene.json"
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        return path

def build_scene_spec(decomposition: Decomposition, feasibility: Feasibility,
                     plan: dict[str, Any] | None = None) -> SceneSpec:
    plan = plan or {}
    notes = str((plan.get("human_labels") or {}).get("notes") or "").lower()
    environment = "simple_platform"
    for token, name in [("hospital", "hospital_template"), ("obby", "simple_obby"),
                        ("city", "city_template"), ("horror", "horror_corridor")]:
        if token in notes:
            environment = name
    scale = {"height": 1.0, "width": 1.0, "head": 1.0, "body_type": 0.0}
    if any(x in notes for x in ("giant", "large head", "oversized", "679%")):
        scale["head"] = 6.79
    gui = []
    if any(x in notes for x in ("slider", "size ui", "scale")):
        gui.append({"type": "slider", "name": "ScaleSlider", "label": "Size",
                    "min": .5, "max": 7.0, "value": scale["head"], "position": "left_center"})
    timeline = [
        {"time": 0.0, "action": "spawn_avatar", "target": "MainAvatar"},
        {"time": .05, "action": "set_avatar_scale", "target": "MainAvatar", "properties": scale},
    ]
    mapping = {"hard_cut": "camera_cut", "zoom_transition": "camera_zoom_pulse",
               "whip_pan_horizontal": "camera_whip_horizontal",
               "whip_pan_vertical": "camera_whip_vertical"}
    for item in decomposition.transitions:
        if item.kind in mapping:
            timeline.append({"time": item.time, "action": mapping[item.kind], "target": "Camera"})
    unresolved = list(feasibility.exact_inputs_needed)
    if not notes:
        unresolved.append("add the mechanic and environment to Analysis Review notes")
    result = SceneSpec(
        decomposition.source_file, "1.0", feasibility.recommended_engine,
        decomposition.duration, {"template": environment, "lighting": "bright_neutral"},
        [{"name": "MainAvatar", "rig": "R15", "appearance": "generic_original_avatar",
          "scale": scale, "animation": "idle_or_walk", "spawn": [0, 2, 0]}],
        {"mode": "scriptable", "shot": "third_person_rear", "position": [0, 5, -10],
         "target": "MainAvatar.HumanoidRootPart", "movement": "slow_push_in"},
        gui, sorted(timeline, key=lambda x: x["time"]),
        {"transitions": [{"time": x.time, "type": x.kind, "confidence": x.confidence}
                         for x in decomposition.transitions],
         "sound_effects": [{"time": x.start, "duration": round(x.end - x.start, 3),
                            "family": x.family, "confidence": x.confidence}
                           for x in decomposition.sound_effects],
         "overlays": decomposition.visual_events,
         "voiceover_required": bool(decomposition.audio_layers.get("probable_voiceover"))},
        list(dict.fromkeys(unresolved)), feasibility.overall_score
    )
    result.save()
    return result
