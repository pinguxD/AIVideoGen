from __future__ import annotations

from flask import request

from .audio_autopilot import run_audio_autopilot
from .reference_library import list_reference_runs


def register_audio_autopilot_routes(app, page, esc) -> None:
    @app.route("/audio-autopilot")
    def audio_autopilot_page():
        runs = [
            item
            for item in list_reference_runs(limit=500)
            if str(item.get("status") or "") == "ANALYZED"
        ]

        cards = []
        for item in runs:
            source_name = str(item.get("source_name") or "")
            cards.append(
                f"""
                <div class="card">
                  <h3>{esc(source_name)}</h3>
                  <p>
                    The AI profiles the reference voice, chooses the closest
                    available ElevenLabs voice, generates narration, and creates
                    every detected sound effect automatically.
                  </p>

                  <form method="post"
                        action="/audio-autopilot/generate">
                    <input type="hidden"
                           name="source_name"
                           value="{esc(source_name)}">

                    <label>Original narration script</label>
                    <textarea name="narration_text"
                              rows="8"
                              style="width:100%"
                              placeholder="Paste the original script for now. Automatic script writing comes next."></textarea>

                    <label>Optional preferred ElevenLabs voice ID</label>
                    <input name="preferred_voice_id"
                           placeholder="Leave empty for automatic selection">

                    <button type="submit">
                      Run full audio autopilot
                    </button>
                  </form>
                </div>
                """
            )

        body = """
        <h1>Audio Intelligence Autopilot</h1>
        <div class="card">
          <p>
            This replaces the old “identify unknown sounds” and “choose TTS”
            warnings with actual automatic generation.
          </p>
        </div>
        """ + "".join(cards)

        return page(
            "Audio Intelligence Autopilot",
            body,
            "/audio-autopilot",
        )

    @app.route("/audio-autopilot/generate", methods=["POST"])
    def audio_autopilot_generate():
        source_name = str(request.form.get("source_name") or "")
        try:
            result = run_audio_autopilot(
                source_name=source_name,
                narration_text=str(
                    request.form.get("narration_text") or ""
                ),
                preferred_voice_id=(
                    str(
                        request.form.get("preferred_voice_id")
                        or ""
                    ).strip()
                    or None
                ),
            )
        except Exception as exc:
            return page(
                "Audio Autopilot failed",
                f"""
                <h1>Audio Autopilot failed</h1>
                <div class="card"><pre>{esc(exc)}</pre></div>
                <a class="btn" href="/audio-autopilot">Back</a>
                """,
                "/audio-autopilot",
            ), 500

        profile = result.get("voice_profile") or {}
        choice = result.get("voice_choice") or {}

        effects = "".join(
            f"""
            <tr>
              <td>{esc(item.get("start", 0))}</td>
              <td>{esc(item.get("family", ""))}</td>
              <td>{esc(item.get("prompt", ""))}</td>
              <td>
                <span class="path">
                  {esc(item.get("audio_file", ""))}
                </span>
              </td>
            </tr>
            """
            for item in result.get("generated_sound_effects", [])
        ) or '<tr><td colspan="4">No effects were detected.</td></tr>'

        missing = "<br>".join(
            esc(item) for item in result.get("missing", [])
        ) or "Nothing missing."

        body = f"""
        <h1>Audio Autopilot result</h1>

        <div class="grid">
          <div class="card">
            <div class="score">{esc(profile.get("estimated_wpm", 0))}</div>
            <p class="stat-label">Estimated WPM</p>
          </div>
          <div class="card">
            <div class="score">{esc(profile.get("delivery", ""))}</div>
            <p class="stat-label">Voice delivery</p>
          </div>
          <div class="card">
            <div class="score">{esc(choice.get("name", ""))}</div>
            <p class="stat-label">Selected voice</p>
          </div>
        </div>

        <div class="card">
          <p><b>Ready for mix:</b>
             {esc(result.get("ready_for_mix"))}</p>
          <p><b>Voice confidence:</b>
             {esc(profile.get("confidence", 0))}%</p>
          <p><b>Voice reasons:</b><br>
             {"<br>".join(esc(x) for x in choice.get("reasons", []))}
          </p>
          <p><b>Voice-over file:</b>
             <span class="path">
               {esc(result.get("voiceover_file", "") or "Not generated")}
             </span>
          </p>
          <p><b>Missing:</b><br>{missing}</p>
          <p><b>Autopilot output:</b>
             <span class="path">{esc(result.get("output_path", ""))}</span>
          </p>
        </div>

        <div class="card">
          <h2>Generated sound effects</h2>
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Family</th>
                <th>Generation prompt</th>
                <th>File</th>
              </tr>
            </thead>
            <tbody>{effects}</tbody>
          </table>
        </div>

        <a class="btn" href="/audio-autopilot">Back</a>
        """

        return page(
            "Audio Autopilot result",
            body,
            "/audio-autopilot",
        )
