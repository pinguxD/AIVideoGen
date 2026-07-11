from __future__ import annotations

from flask import jsonify, request

from .reference_library import list_reference_runs
from .roblox_plugin_bridge import (
    complete_job,
    create_plugin_job,
    fail_job,
    list_plugin_jobs,
    next_pending_job,
)


def register_roblox_plugin_routes(app, page, esc) -> None:
    @app.route("/roblox-plugin")
    def roblox_plugin_page():
        references = [
            item
            for item in list_reference_runs(limit=500)
            if str(item.get("status") or "") == "ANALYZED"
        ]

        cards = []
        for item in references:
            source_name = str(item.get("source_name") or "")
            cards.append(
                f"""
                <div class="card">
                  <h3>{esc(source_name)}</h3>
                  <p>
                    Queue the scene specification, generated controller, and
                    Roblox Brain plan for the Studio plugin.
                  </p>
                  <form method="post"
                        action="/roblox-plugin/create-job">
                    <input type="hidden"
                           name="source_name"
                           value="{esc(source_name)}">
                    <button type="submit">
                      Queue scene for Studio plugin
                    </button>
                  </form>
                </div>
                """
            )

        jobs = "".join(
            f"""
            <tr>
              <td>{esc(job.get("source_name", ""))}</td>
              <td>{esc(job.get("status", ""))}</td>
              <td>{esc(job.get("job_id", ""))}</td>
              <td>
                {esc((job.get("roblox_brain") or {}).get("generation_mode", ""))}
              </td>
              <td>{esc(job.get("message", ""))}</td>
            </tr>
            """
            for job in list_plugin_jobs(100)
        ) or '<tr><td colspan="5">No plugin jobs yet.</td></tr>'

        body = f"""
        <h1>Roblox Studio Plugin Bridge</h1>
        {"".join(cards)}
        <div class="card">
          <h2>Plugin jobs</h2>
          <table>
            <thead>
              <tr>
                <th>Reference</th>
                <th>Status</th>
                <th>Job ID</th>
                <th>Brain mode</th>
                <th>Message</th>
              </tr>
            </thead>
            <tbody>{jobs}</tbody>
          </table>
        </div>
        """

        return page(
            "Roblox Studio Plugin Bridge",
            body,
            "/roblox-plugin",
        )

    @app.route("/roblox-plugin/create-job", methods=["POST"])
    def roblox_plugin_create_job():
        source_name = str(request.form.get("source_name") or "").strip()
        try:
            job = create_plugin_job(source_name)
        except Exception as exc:
            return page(
                "Job failed",
                f"""
                <h1>Could not create plugin job</h1>
                <div class="card"><pre>{esc(exc)}</pre></div>
                <a class="btn" href="/roblox-plugin">Back</a>
                """,
                "/roblox-plugin",
            ), 500

        return page(
            "Job queued",
            f"""
            <h1>Scene queued</h1>
            <div class="card">
              <p><b>Reference:</b> {esc(job.source_name)}</p>
              <p><b>Job ID:</b> {esc(job.job_id)}</p>
              <p><b>Brain mode:</b>
                 {esc(job.roblox_brain.get("generation_mode", ""))}</p>
              <p>
                The Part 2 Roblox Brain plan is now attached to the job.
              </p>
            </div>
            <a class="btn" href="/roblox-plugin">Back</a>
            """,
            "/roblox-plugin",
        )

    @app.route("/api/roblox-plugin/next-job")
    def roblox_plugin_next_job():
        job = next_pending_job()
        if job is None:
            return jsonify({"ok": True, "job": None})

        return jsonify(
            {
                "ok": True,
                "job": {
                    "job_id": job.job_id,
                    "source_name": job.source_name,
                    "scene_spec": job.scene_spec,
                    "roblox_brain": job.roblox_brain,
                    "generated_lua": job.generated_lua,
                },
            }
        )

    @app.route(
        "/api/roblox-plugin/jobs/<job_id>/complete",
        methods=["POST"],
    )
    def roblox_plugin_complete(job_id: str):
        payload = request.get_json(silent=True) or {}
        job = complete_job(
            job_id,
            str(payload.get("message") or "Imported successfully"),
        )
        return jsonify({"ok": True, "status": job.status})

    @app.route(
        "/api/roblox-plugin/jobs/<job_id>/fail",
        methods=["POST"],
    )
    def roblox_plugin_fail(job_id: str):
        payload = request.get_json(silent=True) or {}
        job = fail_job(
            job_id,
            str(payload.get("message") or "Unknown plugin error"),
        )
        return jsonify({"ok": True, "status": job.status})
