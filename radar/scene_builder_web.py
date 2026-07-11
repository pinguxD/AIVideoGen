from __future__ import annotations

from flask import request

from .reference_library import list_reference_runs
from .scene_builder_engine import (
    build_scene_package,
    list_scene_builds,
)


def register_scene_builder_routes(app, page, esc) -> None:
    @app.route("/scene-builder")
    def scene_builder_page():
        references = [
            item
            for item in list_reference_runs(limit=500)
            if str(item.get("status") or "") == "ANALYZED"
        ]

        cards = "".join(
            f"""
            <div class="card">
              <h3>{esc(str(item.get("source_name") or ""))}</h3>
              <p>
                Generate modular Luau builders from the completed Part 2A
                Video Blueprint.
              </p>
              <form method="post" action="/scene-builder/build">
                <input type="hidden"
                       name="source_name"
                       value="{esc(str(item.get("source_name") or ""))}">
                <button type="submit">
                  Build Part 3A scene package
                </button>
              </form>
            </div>
            """
            for item in references
        )

        rows = "".join(
            f"""
            <tr>
              <td>{esc(item.get("source_name", ""))}</td>
              <td>{esc(item.get("status", ""))}</td>
              <td>{esc(item.get("build_id", ""))}</td>
              <td>{esc(len(item.get("results") or []))}</td>
              <td>{esc(len(item.get("missing_builders") or []))}</td>
              <td>
                <span class="path">
                  {esc(item.get("package_dir", ""))}
                </span>
              </td>
            </tr>
            """
            for item in list_scene_builds()
        ) or '<tr><td colspan="6">No Part 3A builds yet.</td></tr>'

        body = f"""
        <h1>Roblox Scene Builder — Part 3A</h1>

        <div class="card">
          <p>
            Blueprint → modular builders → timeline → Studio handoff package.
          </p>
        </div>

        {cards}

        <div class="card">
          <h2>Build history</h2>
          <table>
            <thead>
              <tr>
                <th>Reference</th>
                <th>Status</th>
                <th>Build</th>
                <th>Builders</th>
                <th>Missing</th>
                <th>Package</th>
              </tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>
        </div>
        """

        return page(
            "Roblox Scene Builder",
            body,
            "/scene-builder",
        )

    @app.route("/scene-builder/build", methods=["POST"])
    def scene_builder_build():
        source_name = str(
            request.form.get("source_name") or ""
        ).strip()

        try:
            build = build_scene_package(source_name)
        except Exception as exc:
            return page(
                "Scene build failed",
                f"""
                <h1>Scene build failed</h1>
                <div class="card"><pre>{esc(exc)}</pre></div>
                <a class="btn" href="/scene-builder">Back</a>
                """,
                "/scene-builder",
            ), 500

        result_rows = "".join(
            f"""
            <tr>
              <td>{esc(result.phase)}</td>
              <td>{esc(result.builder_id)}</td>
              <td>{esc(result.status)}</td>
              <td>{esc(result.message)}</td>
              <td>{"<br>".join(esc(w) for w in result.warnings)}</td>
            </tr>
            """
            for result in build.results
        )

        artifact_rows = "".join(
            f"""
            <tr>
              <td>{esc(item.kind)}</td>
              <td>{esc(item.name)}</td>
              <td><span class="path">{esc(item.path)}</span></td>
            </tr>
            """
            for item in build.artifacts
        )

        missing = "<br>".join(
            esc(item) for item in build.missing_builders
        ) or "None"

        warnings = "<br>".join(
            esc(item) for item in build.warnings
        ) or "None"

        body = f"""
        <h1>Part 3A build result</h1>

        <div class="grid">
          <div class="card">
            <div class="score">{esc(build.status)}</div>
            <p>Build status</p>
          </div>
          <div class="card">
            <div class="score">{esc(len(build.results))}</div>
            <p>Builders executed</p>
          </div>
          <div class="card">
            <div class="score">{esc(len(build.artifacts))}</div>
            <p>Artifacts generated</p>
          </div>
        </div>

        <div class="card">
          <p><b>Package:</b>
             <span class="path">{esc(build.package_dir)}</span></p>
          <p><b>Missing builders:</b><br>{missing}</p>
          <p><b>Warnings:</b><br>{warnings}</p>
        </div>

        <div class="card">
          <h2>Builder results</h2>
          <table>
            <thead>
              <tr>
                <th>Phase</th>
                <th>Builder</th>
                <th>Status</th>
                <th>Message</th>
                <th>Warnings</th>
              </tr>
            </thead>
            <tbody>{result_rows}</tbody>
          </table>
        </div>

        <div class="card">
          <h2>Generated artifacts</h2>
          <table>
            <thead>
              <tr><th>Type</th><th>Name</th><th>Path</th></tr>
            </thead>
            <tbody>{artifact_rows}</tbody>
          </table>
        </div>

        <a class="btn" href="/scene-builder">Back</a>
        """

        return page(
            "Part 3A build result",
            body,
            "/scene-builder",
        )
