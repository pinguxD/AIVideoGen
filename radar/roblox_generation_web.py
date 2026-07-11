from __future__ import annotations

from flask import request

from .reference_library import list_reference_runs
from .roblox_studio_bridge import create_and_launch, list_jobs

def register_roblox_generation_routes(app, page, esc) -> None:
    @app.route("/roblox-generation")
    def roblox_generation_page():
        runs = [
            item for item in list_reference_runs(limit=500)
            if str(item.get("status") or "") == "ANALYZED"
        ]

        cards = []
        for item in runs:
            source_name = str(item.get("source_name") or "")
            cards.append(
                f'''
                <div class="card">
                  <h3>{esc(source_name)}</h3>
                  <p>Launch Studio and import the generated scene controller.</p>
                  <form method="post" action="/roblox-generation/launch">
                    <input type="hidden" name="source_name" value="{esc(source_name)}">
                    <button type="submit">Start Roblox generation - Stage 1</button>
                  </form>
                </div>
                '''
            )

        job_rows = "".join(
            f'''
            <tr>
              <td>{esc(job.get("source_name", ""))}</td>
              <td>{esc(job.get("status", ""))}</td>
              <td>{esc(job.get("process_id", ""))}</td>
              <td><span class="path">{esc(job.get("import_script", ""))}</span></td>
              <td>{esc(job.get("error", ""))}</td>
            </tr>
            '''
            for job in list_jobs(50)
        ) or '<tr><td colspan="5">No Studio jobs yet.</td></tr>'

        body = f'''
        <h1>Roblox Studio Generation</h1>
        <div class="card">
          <h2>Stage 1</h2>
          <p>Studio opens and imports GeneratedScene into StarterPlayerScripts. Then press Play.</p>
        </div>
        {"".join(cards) or '<div class="card">No analyzed references found.</div>'}
        <div class="card">
          <h2>Launch history</h2>
          <table>
            <thead><tr><th>Reference</th><th>Status</th><th>PID</th><th>Importer</th><th>Error</th></tr></thead>
            <tbody>{job_rows}</tbody>
          </table>
        </div>
        '''
        return page("Roblox Studio Generation", body, "/roblox-generation")

    @app.route("/roblox-generation/launch", methods=["POST"])
    def roblox_generation_launch():
        source_name = str(request.form.get("source_name") or "").strip()
        if not source_name:
            return page("Launch failed", '<h1>Launch failed</h1><div class="card">No reference selected.</div>', "/roblox-generation"), 400

        try:
            job = create_and_launch(source_name)
        except Exception as exc:
            return page(
                "Studio launch failed",
                f'<h1>Studio launch failed</h1><div class="card"><pre>{esc(exc)}</pre></div><a class="btn" href="/roblox-generation">Back</a>',
                "/roblox-generation",
            ), 500

        body = f'''
        <h1>Roblox Studio launched</h1>
        <div class="card">
          <p><b>Reference:</b> {esc(job.source_name)}</p>
          <p><b>Process ID:</b> {esc(job.process_id)}</p>
          <p><b>Studio:</b> <span class="path">{esc(job.studio_executable)}</span></p>
          <p><b>Template:</b> <span class="path">{esc(job.template_place or "Default Studio baseplate")}</span></p>
          <p><b>Importer:</b> <span class="path">{esc(job.import_script)}</span></p>
          <p><b>Log:</b> <span class="path">{esc(job.output_log)}</span></p>
        </div>
        <div class="card">
          <h2>In Studio</h2>
          <ol>
            <li>Wait for the place to open.</li>
            <li>Open StarterPlayer &gt; StarterPlayerScripts.</li>
            <li>Confirm GeneratedScene exists.</li>
            <li>Press Play.</li>
          </ol>
        </div>
        <a class="btn" href="/roblox-generation">Back</a>
        '''
        return page("Studio launched", body, "/roblox-generation")
