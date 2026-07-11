from __future__ import annotations

from flask import jsonify, request

from .scene_builder_plugin_bridge import (
    available_builds,
    complete_job,
    fail_job,
    list_plugin_jobs,
    next_pending_job,
    package_payload,
    queue_scene_build,
)
from .scene_builder_plugin_launcher import (
    open_plugin_file,
    open_plugin_folder,
    prepare_and_launch,
)


def register_scene_builder_plugin_routes(app, page, esc) -> None:
    @app.route("/scene-builder-plugin")
    def scene_builder_plugin_page():
        build_cards = "".join(
            f"""
            <div class="card">
              <h3>{esc(build.get("source_name", ""))}</h3>
              <p>
                <b>Build:</b> {esc(build.get("build_id", ""))}<br>
                <b>Status:</b> {esc(build.get("status", ""))}<br>
                <b>Artifacts:</b> {esc(len(build.get("artifacts") or []))}
              </p>
              <form method="post" action="/scene-builder-plugin/queue-and-open">
                <input type="hidden" name="build_id" value="{esc(build.get("build_id", ""))}">
                <button type="submit">
                  Queue + Open Plugin + Launch Studio
                </button>
              </form>
              <form method="post" action="/scene-builder-plugin/queue" style="margin-top:8px">
                <input type="hidden" name="build_id" value="{esc(build.get("build_id", ""))}">
                <button type="submit">
                  Queue only
                </button>
              </form>
            </div>
            """
            for build in available_builds(100)
        ) or """
        <div class="card">
          No successful Part 3A packages found. Build one from
          Roblox Scene Builder first.
        </div>
        """

        job_rows = "".join(
            f"""
            <tr>
              <td>{esc(job.get("source_name", ""))}</td>
              <td>{esc(job.get("build_id", ""))}</td>
              <td>{esc(job.get("status", ""))}</td>
              <td>{esc(job.get("job_id", ""))}</td>
              <td>{esc(job.get("message", ""))}</td>
            </tr>
            """
            for job in list_plugin_jobs(100)
        ) or '<tr><td colspan="5">No Studio installation jobs yet.</td></tr>'

        body = f"""
        <h1>Roblox Studio Installer — Part 3B</h1>

        <div class="card">
          <h2>One-time plugin setup</h2>
          <p>
            The program can generate and open the plugin file and launch Studio.
            Roblox still requires you to save it as a Local Plugin once for security.
            After that, future builds only need Queue + Fetch &amp; Install.
          </p>
          <form method="post" action="/scene-builder-plugin/open-plugin">
            <button type="submit">Generate &amp; Open Plugin File</button>
          </form>
          <form method="post" action="/scene-builder-plugin/open-plugin-folder" style="margin-top:8px">
            <button type="submit">Open Generated Plugin Folder</button>
          </form>
        </div>

        {build_cards}

        <div class="card">
          <h2>Installation jobs</h2>
          <table>
            <thead>
              <tr>
                <th>Reference</th><th>Build</th><th>Status</th>
                <th>Job</th><th>Message</th>
              </tr>
            </thead>
            <tbody>{job_rows}</tbody>
          </table>
        </div>
        """

        return page(
            "Roblox Studio Installer",
            body,
            "/scene-builder-plugin",
        )

    def _queue(build_id: str):
        if not build_id:
            raise ValueError("No Part 3A build was selected.")
        return queue_scene_build(build_id)

    @app.route("/scene-builder-plugin/queue", methods=["POST"])
    def scene_builder_plugin_queue():
        build_id = str(request.form.get("build_id") or "").strip()
        try:
            job = _queue(build_id)
        except Exception as exc:
            return page(
                "Queue failed",
                f'<h1>Could not queue package</h1><div class="card"><pre>{esc(exc)}</pre></div>',
                "/scene-builder-plugin",
            ), 500

        return page(
            "Package queued",
            f"""
            <h1>Package queued</h1>
            <div class="card">
              <p><b>Build:</b> {esc(job.build_id)}</p>
              <p>Open Studio and click <b>AIVideoGen → Fetch &amp; Install</b>.</p>
            </div>
            <a class="btn" href="/scene-builder-plugin">Back</a>
            """,
            "/scene-builder-plugin",
        )

    @app.route("/scene-builder-plugin/queue-and-open", methods=["POST"])
    def scene_builder_plugin_queue_and_open():
        build_id = str(request.form.get("build_id") or "").strip()
        try:
            job = _queue(build_id)
            launch = prepare_and_launch(
                open_plugin=True,
                launch_roblox_studio=True,
            )
        except Exception as exc:
            return page(
                "Launch failed",
                f'<h1>Could not prepare Studio</h1><div class="card"><pre>{esc(exc)}</pre></div>',
                "/scene-builder-plugin",
            ), 500

        warnings = "<br>".join(
            esc(item) for item in launch.get("warnings", [])
        ) or "None"

        return page(
            "Studio prepared",
            f"""
            <h1>Package queued and Studio prepared</h1>
            <div class="card">
              <p><b>Build:</b> {esc(job.build_id)}</p>
              <p><b>Plugin file:</b> <span class="path">{esc(launch.get("plugin_path", ""))}</span></p>
              <p><b>Plugin opened:</b> {esc(launch.get("plugin_opened", False))}</p>
              <p><b>Studio launched:</b> {esc(launch.get("studio_launched", False))}</p>
              <p><b>Warnings:</b><br>{warnings}</p>
            </div>
            <div class="card">
              <h2>First time only</h2>
              <p>
                Copy the opened Lua file into a Script in Studio and choose
                <b>Plugins → Save as Local Plugin</b>. Restart Studio once.
              </p>
              <p>
                After installation, click <b>AIVideoGen → Fetch &amp; Install</b>.
              </p>
            </div>
            <a class="btn" href="/scene-builder-plugin">Back</a>
            """,
            "/scene-builder-plugin",
        )

    @app.route("/scene-builder-plugin/open-plugin", methods=["POST"])
    def scene_builder_plugin_open_plugin():
        try:
            path = open_plugin_file()
        except Exception as exc:
            return page(
                "Open failed",
                f'<h1>Could not open plugin</h1><div class="card"><pre>{esc(exc)}</pre></div>',
                "/scene-builder-plugin",
            ), 500

        return page(
            "Plugin opened",
            f"""
            <h1>Plugin file generated and opened</h1>
            <div class="card">
              <span class="path">{esc(path)}</span>
            </div>
            <a class="btn" href="/scene-builder-plugin">Back</a>
            """,
            "/scene-builder-plugin",
        )

    @app.route("/scene-builder-plugin/open-plugin-folder", methods=["POST"])
    def scene_builder_plugin_open_plugin_folder():
        try:
            path = open_plugin_folder()
        except Exception as exc:
            return page(
                "Open failed",
                f'<h1>Could not open folder</h1><div class="card"><pre>{esc(exc)}</pre></div>',
                "/scene-builder-plugin",
            ), 500

        return page(
            "Folder opened",
            f"""
            <h1>Generated plugin folder opened</h1>
            <div class="card"><span class="path">{esc(path)}</span></div>
            <a class="btn" href="/scene-builder-plugin">Back</a>
            """,
            "/scene-builder-plugin",
        )

    @app.route("/api/scene-builder-plugin/next-job")
    def scene_builder_plugin_next_job():
        job = next_pending_job()
        if job is None:
            return jsonify({"ok": True, "job": None})
        try:
            payload = package_payload(job)
        except Exception as exc:
            fail_job(job.job_id, str(exc))
            return jsonify({"ok": False, "error": str(exc)}), 500
        return jsonify({"ok": True, "job": payload})

    @app.route("/api/scene-builder-plugin/jobs/<job_id>/complete", methods=["POST"])
    def scene_builder_plugin_complete(job_id: str):
        payload = request.get_json(silent=True) or {}
        job = complete_job(
            job_id,
            str(payload.get("message") or "Studio package installed successfully."),
        )
        return jsonify({"ok": True, "status": job.status})

    @app.route("/api/scene-builder-plugin/jobs/<job_id>/fail", methods=["POST"])
    def scene_builder_plugin_fail(job_id: str):
        payload = request.get_json(silent=True) or {}
        job = fail_job(
            job_id,
            str(payload.get("message") or "Unknown Studio error"),
        )
        return jsonify({"ok": True, "status": job.status})
