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
                <b>Artifacts:</b>
                {esc(len(build.get("artifacts") or []))}
              </p>
              <form method="post"
                    action="/scene-builder-plugin/queue">
                <input type="hidden"
                       name="build_id"
                       value="{esc(build.get("build_id", ""))}">
                <button type="submit">
                  Queue package for Roblox Studio
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
          <p>
            Queue a Part 3A package here, then open Roblox Studio and click
            <b>AIVideoGen → Fetch &amp; Install</b>.
          </p>
        </div>

        {build_cards}

        <div class="card">
          <h2>Installation jobs</h2>
          <table>
            <thead>
              <tr>
                <th>Reference</th>
                <th>Build</th>
                <th>Status</th>
                <th>Job</th>
                <th>Message</th>
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

    @app.route(
        "/scene-builder-plugin/queue",
        methods=["POST"],
    )
    def scene_builder_plugin_queue():
        build_id = str(
            request.form.get("build_id") or ""
        ).strip()

        try:
            job = queue_scene_build(build_id)
        except Exception as exc:
            return page(
                "Queue failed",
                f"""
                <h1>Could not queue Studio package</h1>
                <div class="card"><pre>{esc(exc)}</pre></div>
                <a class="btn" href="/scene-builder-plugin">Back</a>
                """,
                "/scene-builder-plugin",
            ), 500

        return page(
            "Package queued",
            f"""
            <h1>Package queued for Roblox Studio</h1>
            <div class="card">
              <p><b>Reference:</b> {esc(job.source_name)}</p>
              <p><b>Build:</b> {esc(job.build_id)}</p>
              <p><b>Job:</b> {esc(job.job_id)}</p>
              <p>
                In Studio click
                <b>AIVideoGen → Fetch &amp; Install</b>.
              </p>
            </div>
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
            return jsonify(
                {
                    "ok": False,
                    "error": str(exc),
                }
            ), 500

        return jsonify(
            {
                "ok": True,
                "job": payload,
            }
        )

    @app.route(
        "/api/scene-builder-plugin/jobs/<job_id>/complete",
        methods=["POST"],
    )
    def scene_builder_plugin_complete(job_id: str):
        payload = request.get_json(silent=True) or {}
        job = complete_job(
            job_id,
            str(
                payload.get("message")
                or "Studio package installed successfully."
            ),
        )
        return jsonify({"ok": True, "status": job.status})

    @app.route(
        "/api/scene-builder-plugin/jobs/<job_id>/fail",
        methods=["POST"],
    )
    def scene_builder_plugin_fail(job_id: str):
        payload = request.get_json(silent=True) or {}
        job = fail_job(
            job_id,
            str(payload.get("message") or "Unknown Studio error"),
        )
        return jsonify({"ok": True, "status": job.status})
