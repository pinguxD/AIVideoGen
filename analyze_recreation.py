from __future__ import annotations
import argparse, json
from radar.recreation_orchestrator import run
parser = argparse.ArgumentParser()
parser.add_argument("video")
parser.add_argument("--source-name", default="")
parser.add_argument("--sample-every", type=float, default=.2)
args = parser.parse_args()
result = run(args.video, args.source_name or None, max(.1, args.sample_every))
f = result["feasibility"]
print(json.dumps({
    "verdict": f["verdict"],
    "score": f["overall_score"],
    "engine": f["recommended_engine"],
    "prerecorded_footage_required": f["prerecorded_footage_required"],
    "missing": f["exact_inputs_needed"],
    "lua": result["lua_path"],
    "bundle": result["summary_path"],
}, indent=2))
