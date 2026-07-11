from __future__ import annotations

from flask import request, send_file

from .full_video_analyzer import BASE
from .map_analyzer import analyze_map, load_map_analysis
from .reference_library import list_reference_runs


def register_map_analyzer_routes(app, page, esc) -> None:
    @app.route("/map-analyzer")
    def map_analyzer_page():
        references = [item for item in list_reference_runs(limit=500) if str(item.get("status") or "") == "ANALYZED"]
        cards = []
        for item in references:
            source_name = str(item.get("source_name") or "")
            result = load_map_analysis(source_name)
            summary = ""
            if result:
                summary = f"<p><b>Scene:</b> {esc(result.scene_family)} · <b>Platforms:</b> {esc(result.estimated_platform_count)} · <b>Indoor:</b> {esc(result.indoor_probability)}% · <b>Confidence:</b> {esc(result.confidence)}%</p>"
            cards.append(f'''<div class="card"><h3>{esc(source_name)}</h3>{summary}<form method="post" action="/map-analyzer/analyze"><input type="hidden" name="source_name" value="{esc(source_name)}"><button type="submit">Analyze Map Geometry</button></form></div>''')
        return page("Advanced Map Analyzer", f'''<h1>Advanced Map Analyzer</h1><div class="card"><p>Samples the reference, detects floors, walls, corridors, platforms, palette, openness and camera travel, then creates reconstruction requirements.</p></div>{"".join(cards)}''', "/map-analyzer")

    @app.route("/map-analyzer/analyze", methods=["POST"])
    def map_analyzer_analyze():
        source_name = str(request.form.get("source_name") or "").strip()
        try:
            result = analyze_map(source_name)
        except Exception as exc:
            return page("Map analysis failed", f'<h1>Map analysis failed</h1><div class="card"><pre>{esc(exc)}</pre></div><a class="btn" href="/map-analyzer">Back</a>', "/map-analyzer"), 500
        requirements = "".join(f"<tr><td>{esc(key)}</td><td>{esc(value)}</td></tr>" for key, value in result.map_requirements.items())
        observations = "".join(f'<tr><td>{esc(item.frame_time)}</td><td>{esc(item.kind)}</td><td>{esc(item.confidence)}%</td><td>{esc(item.x)}, {esc(item.y)}</td><td>{esc(item.width)} × {esc(item.height)}</td></tr>' for item in result.platform_observations[:20]) or '<tr><td colspan="5">No strong platform observations.</td></tr>'
        rules = "".join(f"<li>{esc(rule)}</li>" for rule in result.reconstruction_rules)
        body = f'''<h1>Map analysis result</h1><div class="grid"><div class="card"><div class="score">{esc(result.scene_family)}</div><p>Scene family</p></div><div class="card"><div class="score">{esc(result.estimated_platform_count)}</div><p>Estimated platforms</p></div><div class="card"><div class="score">{esc(result.confidence)}%</div><p>Confidence</p></div></div><div class="card"><p><b>Environment:</b> {esc(result.environment_type)}</p><p><b>Indoor:</b> {esc(result.indoor_probability)}%</p><p><b>Outdoor:</b> {esc(result.outdoor_probability)}%</p><p><b>Platform probability:</b> {esc(result.platform_probability)}%</p><p><b>Corridor probability:</b> {esc(result.corridor_probability)}%</p><p><b>Camera travel:</b> {esc(result.camera_travel)}</p><a class="btn" href="/map-analyzer/contact-sheet/{esc(result.source_name)}">Open annotated contact sheet</a></div><div class="card"><h2>Map requirements</h2><table><tbody>{requirements}</tbody></table></div><div class="card"><h2>Detected platform evidence</h2><table><thead><tr><th>Time</th><th>Kind</th><th>Confidence</th><th>Position</th><th>Size</th></tr></thead><tbody>{observations}</tbody></table></div><div class="card"><h2>Reconstruction rules</h2><ul>{rules}</ul></div><a class="btn" href="/map-analyzer">Back</a>'''
        return page("Map analysis result", body, "/map-analyzer")

    @app.route("/map-analyzer/contact-sheet/<path:source_name>")
    def map_analyzer_contact_sheet(source_name: str):
        result = load_map_analysis(source_name)
        if not result or not result.contact_sheet_path:
            return "Contact sheet not found.", 404
        path = BASE / result.contact_sheet_path
        return send_file(path, mimetype="image/jpeg") if path.exists() else (f"Missing: {path}", 404)
