from __future__ import annotations

from pathlib import Path
from flask import request, send_file

from .short_producer import (
    audio_candidates,
    latest_generated_places,
    list_jobs,
    produce_short,
)


def register_short_producer_routes(app, page, esc) -> None:
    @app.route("/short-producer")
    def short_producer_page():
        places = latest_generated_places(50)
        audio = audio_candidates(100)

        place_options = "".join(
            f'<option value="{esc(item["place_path"])}">'
            f'{esc(item["source_name"])} — {esc(item["place_path"])}'
            "</option>"
            for item in places
        )

        audio_options = (
            '<option value="">No audio yet — video only</option>'
            + "".join(
                f'<option value="{esc(item["path"])}">'
                f'{esc(item["name"])}</option>'
                for item in audio
            )
        )

        job_rows = "".join(
            f'''
            <tr>
              <td>{esc(job.get("source_name", ""))}</td>
              <td>{esc(job.get("status", ""))}</td>
              <td>{esc(job.get("duration", ""))}s</td>
              <td>{esc(job.get("error", ""))}</td>
              <td>{
                f'<a class="btn" href="/short-producer/video/{esc(job.get("job_id", ""))}">Open MP4</a>'
                if job.get("status") == "COMPLETED"
                else ""
              }</td>
            </tr>
            '''
            for job in list_jobs(100)
        ) or '<tr><td colspan="5">No recording jobs yet.</td></tr>'

        body = f'''
        <h1>Short Producer MVP</h1>
        <div class="card">
          <h2>Record a generated Roblox Short</h2>
          <p>
            Launches the generated place, starts Play mode, records the Studio
            window, crops it to 9:16, and exports a 1080×1920 MP4.
          </p>
          <form method="post" action="/short-producer/produce">
            <p><label>Generated place</label><br>
              <select name="place_path" required style="width:100%">
                {place_options}
              </select>
            </p>
            <p><label>Reference/name</label><br>
              <input name="source_name" value="Creator AI Short" style="width:100%">
            </p>
            <div class="grid">
              <p><label>Short duration</label><br>
                <input type="number" name="duration" value="15" min="3" max="60" step="0.5">
              </p>
              <p><label>Studio launch wait</label><br>
                <input type="number" name="launch_wait" value="12" min="2" max="60" step="1">
              </p>
              <p><label>Play-mode wait</label><br>
                <input type="number" name="play_wait" value="2" min="0.5" max="10" step="0.5">
              </p>
            </div>
            <p><label>Audio track</label><br>
              <select name="audio_path" style="width:100%">{audio_options}</select>
            </p>
            <p><label>Studio window title</label><br>
              <input name="window_title" value="Roblox Studio" style="width:100%">
            </p>
            <button type="submit">Launch, Record &amp; Export Short</button>
          </form>
        </div>
        <div class="card">
          <h2>Recording history</h2>
          <table>
            <thead><tr><th>Name</th><th>Status</th><th>Duration</th><th>Error</th><th>Output</th></tr></thead>
            <tbody>{job_rows}</tbody>
          </table>
        </div>
        '''
        return page("Short Producer MVP", body, "/short-producer")

    @app.route("/short-producer/produce", methods=["POST"])
    def short_producer_produce():
        try:
            job = produce_short(
                source_name=str(request.form.get("source_name") or "Creator AI Short"),
                place_path=str(request.form.get("place_path") or ""),
                duration=float(request.form.get("duration") or 15),
                launch_wait=float(request.form.get("launch_wait") or 12),
                play_wait=float(request.form.get("play_wait") or 2),
                window_title=str(request.form.get("window_title") or "Roblox Studio"),
                audio_path=str(request.form.get("audio_path") or ""),
            )
        except Exception as exc:
            return page(
                "Short production failed",
                f'<h1>Short production failed</h1><div class="card"><pre>{esc(exc)}</pre></div><a class="btn" href="/short-producer">Back</a>',
                "/short-producer",
            ), 500

        return page(
            "Short exported",
            f'''
            <h1>Your first automated Short is exported</h1>
            <div class="card">
              <p><b>Status:</b> {esc(job.status)}</p>
              <p><b>Final MP4:</b> <span class="path">{esc(job.final_video_path)}</span></p>
              <a class="btn" href="/short-producer/video/{esc(job.job_id)}">Open final MP4</a>
            </div>
            <a class="btn" href="/short-producer">Back</a>
            ''',
            "/short-producer",
        )

    @app.route("/short-producer/video/<job_id>")
    def short_producer_video(job_id: str):
        jobs = {str(item.get("job_id")): item for item in list_jobs(500)}
        job = jobs.get(job_id)
        if not job:
            return "Short job not found.", 404

        path = Path(str(job.get("final_video_path") or ""))
        if not path.exists():
            return f"MP4 not found: {path}", 404

        return send_file(path, mimetype="video/mp4", conditional=True)
