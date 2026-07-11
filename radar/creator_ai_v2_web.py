from __future__ import annotations

from flask import request

from .creator_ai_v2_pipeline import generate_complete_recreation, list_runs
from .reference_library import list_reference_runs
from .roblox_template_compiler_v2 import TEMPLATE_PATH, install_template


def register_creator_ai_v2_routes(app, page, esc):
    @app.route("/creator-ai-v2")
    def home():
        references = [item for item in list_reference_runs(limit=500) if str(item.get("status") or "") == "ANALYZED"]
        cards = "".join(f'''<div class="card"><h3>{esc(item.get("source_name", ""))}</h3><p>Analyze visible map geometry, then reconstruct it as a connected playable Roblox level.</p><a class="btn" href="/map-analyzer">Review map analyzer</a><form method="post" action="/creator-ai-v2/generate" style="margin-top:8px"><input type="hidden" name="source_name" value="{esc(item.get("source_name", ""))}"><button type="submit">Analyze Map &amp; Generate Reconstruction</button></form></div>''' for item in references)
        rows = "".join(f'<tr><td>{esc(run.get("source_name", ""))}</td><td>{esc(run.get("status", ""))}</td><td>{esc(len(run.get("stages") or []))}</td><td>{esc(run.get("error", ""))}</td></tr>' for run in list_runs()) or '<tr><td colspan="4">No runs yet.</td></tr>'
        status = "READY" if TEMPLATE_PATH.exists() else "NOT INSTALLED"
        body = f'''<h1>Creator AI v2 — Advanced Map Builder</h1><div class="card"><h2>One-time Roblox template</h2><p><b>Status:</b> {status}</p><form method="post" action="/creator-ai-v2/template" enctype="multipart/form-data"><input type="file" name="template_file" accept=".rbxlx" required><button type="submit">Install Baseplate Template</button></form></div><div class="card"><h2>Builder pipeline</h2><p>Video frames → Map Geometry Analyzer → Platform/Room Evidence → World Planner v2 → Playability Repair → Advanced Map Compiler → Studio</p></div>{cards}<div class="card"><h2>Runs</h2><table><thead><tr><th>Reference</th><th>Status</th><th>Stages</th><th>Error</th></tr></thead><tbody>{rows}</tbody></table></div>'''
        return page("Creator AI v2", body, "/creator-ai-v2")

    @app.route("/creator-ai-v2/template", methods=["POST"])
    def template():
        try:
            path = install_template(request.files["template_file"])
        except Exception as exc:
            return page("Template failed", f'<h1>Template failed</h1><div class="card"><pre>{esc(exc)}</pre></div>', "/creator-ai-v2"), 500
        return page("Template installed", f'<h1>Template installed</h1><div class="card"><span class="path">{esc(path)}</span></div><a class="btn" href="/creator-ai-v2">Continue</a>', "/creator-ai-v2")

    @app.route("/creator-ai-v2/generate", methods=["POST"])
    def generate():
        source = str(request.form.get("source_name") or "").strip()
        try:
            run = generate_complete_recreation(source, True)
        except Exception as exc:
            return page("Generation failed", f'<h1>Generation failed</h1><div class="card"><pre>{esc(exc)}</pre></div><a class="btn" href="/creator-ai-v2">Back</a>', "/creator-ai-v2"), 500
        stage_rows = "".join(f'<tr><td>{esc(stage.name)}</td><td>{esc(stage.status)}</td><td>{esc(stage.message)}</td></tr>' for stage in run.stages)
        compiled = next((stage.output for stage in run.stages if stage.name == "project_compiler"), {})
        return page("Generation complete", f'''<h1>Advanced Roblox map reconstructed</h1><div class="card"><p><b>Status:</b> {esc(run.status)}</p><p><b>Project:</b> <span class="path">{esc(compiled.get("project_dir", ""))}</span></p><p><b>Place:</b> <span class="path">{esc(compiled.get("place_path", ""))}</span></p></div><div class="card"><table><thead><tr><th>Stage</th><th>Status</th><th>Message</th></tr></thead><tbody>{stage_rows}</tbody></table></div><a class="btn" href="/creator-ai-v2">Back</a>''', "/creator-ai-v2")
