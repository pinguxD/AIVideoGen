from __future__ import annotations

from flask import request

from .creator_ai_v2_pipeline import (
    generate_complete_recreation,
    list_runs,
)
from .map_blueprint import load_map_blueprint
from .reference_library import list_reference_runs
from .roblox_template_compiler_v2 import (
    TEMPLATE_PATH,
    install_template,
)


def register_creator_ai_v2_routes(app, page, esc):
    @app.route("/creator-ai-v2")
    def home():
        references = [
            item
            for item in list_reference_runs(limit=500)
            if str(item.get("status") or "") == "ANALYZED"
        ]

        cards = []
        for item in references:
            source_name = str(item.get("source_name") or "")
            blueprint = load_map_blueprint(source_name)
            status = blueprint.status if blueprint else "NOT BUILT"

            if blueprint and blueprint.status == "APPROVED":
                action = """
                <form method="post"
                      action="/creator-ai-v2/generate">
                  <input type="hidden"
                         name="source_name"
                         value="{source}">
                  <button type="submit">
                    Generate Roblox Place from Approved Blueprint
                  </button>
                </form>
                """.format(source=esc(source_name))
            else:
                action = """
                <a class="btn"
                   href="/map-blueprint">
                   Build or Approve Map Blueprint First
                </a>
                """

            cards.append(
                """
                <div class="card">
                  <h3>{source}</h3>
                  <p><b>Map Blueprint:</b> {status}</p>
                  {action}
                </div>
                """.format(
                    source=esc(source_name),
                    status=esc(status),
                    action=action,
                )
            )

        rows = "".join(
            """
            <tr>
              <td>{source}</td>
              <td>{status}</td>
              <td>{stages}</td>
              <td>{error}</td>
            </tr>
            """.format(
                source=esc(run.get("source_name", "")),
                status=esc(run.get("status", "")),
                stages=esc(len(run.get("stages") or [])),
                error=esc(run.get("error", "")),
            )
            for run in list_runs()
        ) or '<tr><td colspan="4">No runs yet.</td></tr>'

        template_status = (
            "READY"
            if TEMPLATE_PATH.exists()
            else "NOT INSTALLED"
        )

        body = """
        <h1>Creator AI v2 — Blueprint-Gated Map Generator</h1>

        <div class="card">
          <h2>One-time Roblox template</h2>
          <p><b>Status:</b> {template_status}</p>
          <form method="post"
                action="/creator-ai-v2/template"
                enctype="multipart/form-data">
            <input type="file"
                   name="template_file"
                   accept=".rbxlx"
                   required>
            <button type="submit">Install Baseplate Template</button>
          </form>
        </div>

        <div class="card">
          <h2>Required pipeline</h2>
          <p>
            Full video → tracked Map Blueprint → review/edit → approval →
            constrained World Plan → Roblox compiler.
          </p>
          <a class="btn" href="/map-blueprint">
            Open Full-Video Map Blueprint
          </a>
        </div>

        {cards}

        <div class="card">
          <h2>Runs</h2>
          <table>
            <thead>
              <tr>
                <th>Reference</th><th>Status</th>
                <th>Stages</th><th>Error</th>
              </tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>
        </div>
        """.format(
            template_status=esc(template_status),
            cards="".join(cards),
            rows=rows,
        )

        return page(
            "Creator AI v2",
            body,
            "/creator-ai-v2",
        )

    @app.route("/creator-ai-v2/template", methods=["POST"])
    def template():
        try:
            path = install_template(request.files["template_file"])
        except Exception as exc:
            return page(
                "Template failed",
                """
                <h1>Template failed</h1>
                <div class="card"><pre>{error}</pre></div>
                """.format(error=esc(exc)),
                "/creator-ai-v2",
            ), 500

        return page(
            "Template installed",
            """
            <h1>Template installed</h1>
            <div class="card">
              <span class="path">{path}</span>
            </div>
            <a class="btn" href="/creator-ai-v2">Continue</a>
            """.format(path=esc(path)),
            "/creator-ai-v2",
        )

    @app.route("/creator-ai-v2/generate", methods=["POST"])
    def generate():
        source = str(request.form.get("source_name") or "").strip()
        try:
            run = generate_complete_recreation(source, True)
        except Exception as exc:
            return page(
                "Generation failed",
                """
                <h1>Generation failed</h1>
                <div class="card"><pre>{error}</pre></div>
                <a class="btn" href="/creator-ai-v2">Back</a>
                """.format(error=esc(exc)),
                "/creator-ai-v2",
            ), 500

        stage_rows = "".join(
            """
            <tr>
              <td>{name}</td>
              <td>{status}</td>
              <td>{message}</td>
            </tr>
            """.format(
                name=esc(stage.name),
                status=esc(stage.status),
                message=esc(stage.message),
            )
            for stage in run.stages
        )
        compiled = next(
            (
                stage.output
                for stage in run.stages
                if stage.name == "project_compiler"
            ),
            {},
        )

        return page(
            "Generation complete",
            """
            <h1>Roblox map generated from approved blueprint</h1>
            <div class="card">
              <p><b>Status:</b> {status}</p>
              <p><b>Project:</b>
                 <span class="path">{project}</span></p>
              <p><b>Place:</b>
                 <span class="path">{place}</span></p>
            </div>
            <div class="card">
              <table>
                <thead>
                  <tr><th>Stage</th><th>Status</th><th>Message</th></tr>
                </thead>
                <tbody>{stage_rows}</tbody>
              </table>
            </div>
            <a class="btn" href="/creator-ai-v2">Back</a>
            """.format(
                status=esc(run.status),
                project=esc(compiled.get("project_dir", "")),
                place=esc(compiled.get("place_path", "")),
                stage_rows=stage_rows,
            ),
            "/creator-ai-v2",
        )
