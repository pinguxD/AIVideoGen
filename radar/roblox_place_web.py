from __future__ import annotations

from flask import request

from .roblox_place_generator import (
    generate_and_open,
    generate_place,
    list_generated_places,
    open_generated_folder,
    open_place_in_studio,
    validate_place_file,
)
from .scene_builder_engine import list_scene_builds


def register_roblox_place_routes(app, page, esc) -> None:
    @app.route("/roblox-place-generator")
    def roblox_place_page():
        builds = [
            item
            for item in list_scene_builds(100)
            if str(item.get("status") or "") != "FAILED"
        ]

        build_cards = "".join(
            f"""
            <div class="card">
              <h3>{esc(build.get("source_name", ""))}</h3>
              <p>
                <b>Part 3A build:</b> {esc(build.get("build_id", ""))}<br>
                <b>Status:</b> {esc(build.get("status", ""))}
              </p>

              <form method="post"
                    action="/roblox-place-generator/generate-open"
                    style="display:inline-block;margin-right:8px">
                <input type="hidden"
                       name="build_id"
                       value="{esc(build.get("build_id", ""))}">
                <button type="submit">
                  Generate Place &amp; Open Studio
                </button>
              </form>

              <form method="post"
                    action="/roblox-place-generator/generate"
                    style="display:inline-block">
                <input type="hidden"
                       name="build_id"
                       value="{esc(build.get("build_id", ""))}">
                <button type="submit">
                  Generate Place Only
                </button>
              </form>
            </div>
            """
            for build in builds
        ) or """
        <div class="card">
          No successful Part 3A package exists yet.
        </div>
        """

        generated_rows = "".join(
            f"""
            <tr>
              <td>{esc(item.get("source_name", ""))}</td>
              <td>{esc(item.get("build_id", ""))}</td>
              <td>
                <span class="path">
                  {esc(item.get("place_path", ""))}
                </span>
              </td>
              <td>
                <form method="post"
                      action="/roblox-place-generator/validate"
                      style="display:inline-block;margin-right:6px">
                  <input type="hidden"
                         name="place_path"
                         value="{esc(item.get("project_place") or item.get("place_path", ""))}">
                  <button type="submit">Validate</button>
                </form>
                <form method="post"
                      action="/roblox-place-generator/open"
                      style="display:inline-block">
                  <input type="hidden"
                         name="place_path"
                         value="{esc(item.get("project_place") or item.get("place_path", ""))}">
                  <button type="submit">Open in Studio</button>
                </form>
              </td>
            </tr>
            """
            for item in list_generated_places(100)
        ) or '<tr><td colspan="4">No places generated yet.</td></tr>'

        body = f"""
        <h1>Roblox Place Generator — Parts 3B + 3C</h1>

        <div class="card">
          <p>
            Part 3B creates and validates a complete Roblox XML place plus a self-contained project folder. Part 3C opens the actual .rbxlx file through Windows first, with official Studio launch fallbacks. No Studio plugin is required.
          </p>

          <form method="post"
                action="/roblox-place-generator/open-folder">
            <button type="submit">Open Generated Places Folder</button>
          </form>
        </div>

        {build_cards}

        <div class="card">
          <h2>Generated places</h2>
          <table>
            <thead>
              <tr>
                <th>Reference</th>
                <th>Build</th>
                <th>Place file</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>{generated_rows}</tbody>
          </table>
        </div>
        """

        return page(
            "Roblox Place Generator",
            body,
            "/roblox-place-generator",
        )

    @app.route(
        "/roblox-place-generator/generate",
        methods=["POST"],
    )
    def roblox_place_generate():
        build_id = str(
            request.form.get("build_id") or ""
        ).strip()

        try:
            result = generate_place(build_id)
        except Exception as exc:
            return page(
                "Place generation failed",
                f"""
                <h1>Place generation failed</h1>
                <div class="card"><pre>{esc(exc)}</pre></div>
                <a class="btn" href="/roblox-place-generator">Back</a>
                """,
                "/roblox-place-generator",
            ), 500

        return page(
            "Place generated",
            f"""
            <h1>Roblox place generated</h1>
            <div class="card">
              <p><b>Reference:</b> {esc(result.source_name)}</p>
              <p><b>Build:</b> {esc(result.build_id)}</p>
              <p><b>Place:</b>
                 <span class="path">{esc(result.place_path)}</span></p>
              <p>
                You can now open it from the generated places table.
              </p>
            </div>
            <a class="btn" href="/roblox-place-generator">Back</a>
            """,
            "/roblox-place-generator",
        )

    @app.route(
        "/roblox-place-generator/generate-open",
        methods=["POST"],
    )
    def roblox_place_generate_open():
        build_id = str(
            request.form.get("build_id") or ""
        ).strip()

        try:
            result = generate_and_open(build_id)
        except Exception as exc:
            return page(
                "Generate and open failed",
                f"""
                <h1>Generate and open failed</h1>
                <div class="card"><pre>{esc(exc)}</pre></div>
                <a class="btn" href="/roblox-place-generator">Back</a>
                """,
                "/roblox-place-generator",
            ), 500

        return page(
            "Studio launched",
            f"""
            <h1>Generated place opened in Roblox Studio</h1>
            <div class="card">
              <p><b>Reference:</b> {esc(result.source_name)}</p>
              <p><b>Build:</b> {esc(result.build_id)}</p>
              <p><b>Place:</b>
                 <span class="path">{esc(result.place_path)}</span></p>
              <p><b>Studio process:</b> {esc(result.studio_pid)}</p>
              <p>
                When Studio finishes loading, the environment, generated
                modules, and GeneratedScene script should already be visible
                in Explorer.
              </p>
            </div>
            <a class="btn" href="/roblox-place-generator">Back</a>
            """,
            "/roblox-place-generator",
        )

    @app.route(
        "/roblox-place-generator/open",
        methods=["POST"],
    )
    def roblox_place_open():
        place_path = str(
            request.form.get("place_path") or ""
        ).strip()

        try:
            pid, _ = open_place_in_studio(place_path)
        except Exception as exc:
            return page(
                "Studio launch failed",
                f"""
                <h1>Studio launch failed</h1>
                <div class="card"><pre>{esc(exc)}</pre></div>
                <a class="btn" href="/roblox-place-generator">Back</a>
                """,
                "/roblox-place-generator",
            ), 500

        return page(
            "Studio launched",
            f"""
            <h1>Roblox Studio launched</h1>
            <div class="card">
              <p><b>Place:</b>
                 <span class="path">{esc(place_path)}</span></p>
              <p><b>Process:</b> {esc(pid)}</p>
            </div>
            <a class="btn" href="/roblox-place-generator">Back</a>
            """,
            "/roblox-place-generator",
        )

    @app.route(
        "/roblox-place-generator/validate",
        methods=["POST"],
    )
    def roblox_place_validate():
        place_path = str(
            request.form.get("place_path") or ""
        ).strip()

        result = validate_place_file(place_path)

        checks = [
            ("Well-formed XML", result.valid_xml),
            ("Workspace present", result.has_workspace),
            ("ReplicatedStorage present", result.has_replicated_storage),
            ("StarterPlayer present", result.has_starter_player),
            ("GeneratedScene present", result.has_generated_scene),
            ("AIVideoGen modules present", result.has_package_modules),
            ("Under 100 MB", result.under_100_mb),
        ]
        check_rows = "".join(
            f"<tr><td>{esc(label)}</td><td>{'PASS' if passed else 'FAIL'}</td></tr>"
            for label, passed in checks
        )
        errors = "<br>".join(esc(x) for x in result.errors) or "None"
        warnings = "<br>".join(esc(x) for x in result.warnings) or "None"

        return page(
            "Place validation",
            f"""
            <h1>Generated place validation</h1>
            <div class="card">
              <p><b>Overall:</b> {'VALID' if result.valid else 'INVALID'}</p>
              <p><b>File:</b> <span class="path">{esc(place_path)}</span></p>
              <p><b>Size:</b> {esc(result.size_bytes)} bytes</p>
            </div>
            <div class="card">
              <table>
                <thead><tr><th>Check</th><th>Result</th></tr></thead>
                <tbody>{check_rows}</tbody>
              </table>
            </div>
            <div class="card">
              <p><b>Errors:</b><br>{errors}</p>
              <p><b>Warnings:</b><br>{warnings}</p>
            </div>
            <a class="btn" href="/roblox-place-generator">Back</a>
            """,
            "/roblox-place-generator",
        )

    @app.route(
        "/roblox-place-generator/open-folder",
        methods=["POST"],
    )
    def roblox_place_open_folder():
        try:
            folder = open_generated_folder()
        except Exception as exc:
            return page(
                "Could not open folder",
                f"""
                <h1>Could not open generated folder</h1>
                <div class="card"><pre>{esc(exc)}</pre></div>
                <a class="btn" href="/roblox-place-generator">Back</a>
                """,
                "/roblox-place-generator",
            ), 500

        return page(
            "Folder opened",
            f"""
            <h1>Generated places folder opened</h1>
            <div class="card">
              <span class="path">{esc(folder)}</span>
            </div>
            <a class="btn" href="/roblox-place-generator">Back</a>
            """,
            "/roblox-place-generator",
        )
