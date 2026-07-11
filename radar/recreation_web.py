from __future__ import annotations
from flask import request
from .reference_library import list_reference_runs
from .recreation_orchestrator import run

def register_recreation_routes(app, page, esc):
    @app.route("/recreation-lab")
    def recreation_lab():
        runs = [x for x in list_reference_runs(500) if str(x.get("status")) == "ANALYZED"]
        cards = []
        for item in runs:
            cards.append(
                '<div class="card"><h3>{}</h3><p>{} - {}%</p>'
                '<form method="post" action="/recreation-lab/analyze">'
                '<input type="hidden" name="source_name" value="{}">'
                '<input type="hidden" name="source_file" value="{}">'
                '<input name="sample_interval" type="number" min=".1" max="1" step=".05" value=".2">'
                '<button>Analyze full recreation feasibility</button></form></div>'.format(
                    esc(item.get("source_name")), esc(item.get("detected_format")),
                    esc(item.get("confidence")), esc(item.get("source_name")),
                    esc(item.get("final_path"))
                )
            )
        body = '<h1>Roblox Recreation Lab</h1><div class="card"><p>Analyzes scenes, transitions, sound effects and whether the Roblox scene can be generated without prerecorded footage.</p></div>' + "".join(cards)
        return page("Roblox Recreation Lab", body, "/recreation-lab")

    @app.route("/recreation-lab/analyze", methods=["POST"])
    def recreation_analyze():
        try:
            result = run(
                request.form.get("source_file", ""),
                request.form.get("source_name", ""),
                max(.1, min(1, float(request.form.get("sample_interval") or .2)))
            )
        except Exception as exc:
            return page("Failed", '<h1>Analysis failed</h1><div class="card"><pre>{}</pre></div>'.format(esc(exc)), "/recreation-lab"), 500
        feasibility = result["feasibility"]
        component_rows = "".join(
            '<tr><td>{}</td><td>{}%</td><td>{}</td><td>{}</td></tr>'.format(
                esc(x["component"]), esc(x["score"]), esc(x["method"]),
                "<br>".join(esc(value) for value in x["missing"])
            ) for x in feasibility["components"]
        )
        transition_rows = "".join(
            '<tr><td>{}</td><td>{}</td><td>{}%</td></tr>'.format(
                esc(x["time"]), esc(x["kind"]), esc(x["confidence"])
            ) for x in result["decomposition"]["transitions"]
        ) or '<tr><td colspan="3">None detected</td></tr>'
        sound_rows = "".join(
            '<tr><td>{}</td><td>{}</td><td>{}%</td></tr>'.format(
                esc(x["start"]), esc(x["family"]), esc(x["confidence"])
            ) for x in result["decomposition"]["sound_effects"]
        ) or '<tr><td colspan="3">None detected</td></tr>'
        body = (
            '<h1>Recreation result</h1>'
            '<div class="grid"><div class="card"><div class="score">{}%</div><p>Self-generation</p></div>'
            '<div class="card"><div class="score">{}</div><p>Verdict</p></div>'
            '<div class="card"><div class="score">{}</div><p>Prerecorded footage required</p></div></div>'
            '<div class="card"><h2>Missing</h2><p>{}</p><p class="path">Lua: {}</p></div>'
            '<div class="card"><h2>Components</h2><table><tr><th>Component</th><th>Score</th><th>Method</th><th>Missing</th></tr>{}</table></div>'
            '<div class="card"><h2>Scene switches</h2><table><tr><th>Time</th><th>Type</th><th>Confidence</th></tr>{}</table></div>'
            '<div class="card"><h2>Sound-effect families</h2><table><tr><th>Time</th><th>Family</th><th>Confidence</th></tr>{}</table></div>'
        ).format(
            esc(feasibility["overall_score"]), esc(feasibility["verdict"]),
            "Yes" if feasibility["prerecorded_footage_required"] else "No",
            "<br>".join(esc(x) for x in feasibility["exact_inputs_needed"]) or "Nothing detected",
            esc(result["lua_path"] or "Not generated"), component_rows,
            transition_rows, sound_rows
        )
        return page("Recreation Result", body, "/recreation-lab")
