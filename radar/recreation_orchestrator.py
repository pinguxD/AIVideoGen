from __future__ import annotations
import json
from dataclasses import asdict
from pathlib import Path
from .full_video_analyzer import BASE
from .analysis_review import load_review_bundle
from .scene_decomposer import decompose_video
from .recreation_feasibility import assess
from .roblox_scene_spec import build_scene_spec
from .roblox_lua_generator import generate_lua

OUT = BASE / "outputs" / "recreation_intelligence"

def load_plan(source_name):
    if not source_name:
        return {}
    bundle = load_review_bundle(source_name)
    corrected = BASE / "outputs" / "corrected_reference_analysis" / f"{bundle['source_key']}.corrected.plan.json"
    return json.loads(corrected.read_text(encoding="utf-8")) if corrected.exists() else bundle.get("plan") or {}

def run(source_file, source_name=None, sample_interval=.2):
    decomposition = decompose_video(source_file, sample_interval)
    plan = load_plan(source_name)
    feasibility = assess(decomposition, plan)
    scene_spec = None
    lua_path = manifest_path = None
    if feasibility.safe_to_generate_scene_spec:
        scene_spec = build_scene_spec(decomposition, feasibility, plan)
        lua_path, manifest_path = generate_lua(asdict(scene_spec))
    result = {
        "decomposition": asdict(decomposition),
        "feasibility": asdict(feasibility),
        "scene_spec": asdict(scene_spec) if scene_spec else None,
        "lua_path": str(lua_path) if lua_path else "",
        "manifest_path": str(manifest_path) if manifest_path else "",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in Path(str(source_file)).stem).strip("_") or "reference"
    path = OUT / f"{safe}.recreation_bundle.json"
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    result["summary_path"] = str(path)
    return result
