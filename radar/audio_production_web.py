from __future__ import annotations

import json
from pathlib import Path

from flask import request

from .audio_production_engine import produce_audio_package
from .full_video_analyzer import BASE
from .reference_library import list_reference_runs


def register_audio_production_routes(app, page, esc) -> None:
    @app.route("/audio-production")
    def audio_production_page():
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
                    Generate the voice-over with ElevenLabs and automatically
                    resolve every detected sound-effect family through the
                    licensed sound library.
                  </p>
                  <form method="post"
                        action="/audio-production/generate">
                    <input type="hidden" name="source_name"
                           value="{esc(source_name)}">

                    <label>Narration script</label>
                    <textarea name="narration_text" rows="8"
                              style="width:100%"
                              placeholder="Paste the final original script here."></textarea>

                    <label>ElevenLabs voice ID</label>
                    <input name="voice_id"
                           placeholder="Uses ELEVENLABS_VOICE_ID when empty">

                    <label>Model ID</label>
                    <input name="model_id"
                           value="eleven_multilingual_v2">

                    <label>Stability</label>
                    <input name="stability" type="number"
                           min="0" max="1" step="0.01" value="0.42">

                    <label>Similarity</label>
                    <input name="similarity_boost" type="number"
                           min="0" max="1" step="0.01" value="0.78">

                    <label>Style</label>
                    <input name="style" type="number"
                           min="0" max="1" step="0.01" value="0.22">

                    <button type="submit">
                      Generate TTS and find sound effects
                    </button>
                  </form>
                </div>
                """
            )

        return page(
            "Audio Production",
            """
            <h1>AI Audio Production</h1>
            <div class="card">
              <p>
                This stage creates the narration and finds distinct, licensed
                effects for the sound events detected by Recreation Lab.
              </p>
            </div>
            """
            + "".join(cards),
            "/audio-production",
        )

    @app.route("/audio-production/generate", methods=["POST"])
    def audio_production_generate():
        source_name = str(request.form.get("source_name") or "")
        try:
            result = produce_audio_package(
                source_name=source_name,
                narration_text=str(
                    request.form.get("narration_text") or ""
                ),
                voice_id=str(request.form.get("voice_id") or "") or None,
                model_id=str(request.form.get("model_id") or "") or None,
                stability=float(
                    request.form.get("stability") or 0.42
                ),
                similarity_boost=float(
                    request.form.get("similarity_boost") or 0.78
                ),
                style=float(request.form.get("style") or 0.22),
                find_sounds=True,
            )
        except Exception as exc:
            return page(
                "Audio generation failed",
                f"""
                <h1>Audio generation failed</h1>
                <div class="card"><pre>{esc(exc)}</pre></div>
                <a class="btn" href="/audio-production">Back</a>
                """,
                "/audio-production",
            ), 500

        voiceover = result.get("voiceover") or {}
        rows = "".join(
            f"""
            <tr>
              <td>{esc(item.get("start", 0))}</td>
              <td>{esc(item.get("requested_family", ""))}</td>
              <td>{esc(item.get("sound_name", ""))}</td>
              <td>{esc(item.get("creator", ""))}</td>
              <td>{esc(item.get("license", ""))}</td>
              <td>{esc(item.get("status", ""))}</td>
            </tr>
            """
            for item in result.get("sound_effects", [])
        ) or '<tr><td colspan="6">No effects were required.</td></tr>'

        missing = "<br>".join(
            esc(item) for item in result.get("missing", [])
        ) or "Nothing missing."

        return page(
            "Audio Package",
            f"""
            <h1>Audio package: {esc(source_name)}</h1>

            <div class="card">
              <p><b>Ready for mix:</b>
                 {esc(result.get("ready_for_audio_mix"))}</p>
              <p><b>Voice-over:</b>
                 <span class="path">
                   {esc(voiceover.get("audio_file", "Not generated"))}
                 </span>
              </p>
              <p><b>Package:</b>
                 <span class="path">
                   {esc(result.get("package_path", ""))}
                 </span>
              </p>
              <p><b>Missing:</b><br>{missing}</p>
            </div>

            <div class="card">
              <h2>Resolved sound effects</h2>
              <table>
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Family</th>
                    <th>Sound</th>
                    <th>Creator</th>
                    <th>License</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>{rows}</tbody>
              </table>
            </div>

            <a class="btn" href="/audio-production">Back</a>
            """,
            "/audio-production",
        )
