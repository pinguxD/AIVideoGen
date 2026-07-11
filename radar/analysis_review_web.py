from __future__ import annotations

from pathlib import Path

from flask import redirect, request

from .analysis_feedback import (
    add_timeline_correction,
    delete_timeline_correction,
    get_learning_stats,
    save_analysis_correction,
)
from .analysis_review import load_review_bundle, write_corrected_bundle
from .analysis_to_creator import create_project_from_analysis
from .reference_library import list_reference_runs


FORMATS = [
    "narrated_fact_list",
    "narrated_story",
    "interactive_guess",
    "sound_replacement",
    "meme_edit",
    "gameplay_caption",
    "manual_complex_edit",
]

HOOK_TYPES = [
    "",
    "question",
    "shock",
    "curiosity_gap",
    "warning",
    "challenge",
    "bold_claim",
    "story_open",
    "visual_surprise",
]

VIDEO_GOALS = [
    "",
    "teach",
    "entertain",
    "make_comment",
    "make_share",
    "build_suspense",
    "tell_story",
    "show_reaction",
]

EMOTIONS = [
    "",
    "curiosity",
    "funny",
    "shock",
    "suspense",
    "fear",
    "nostalgia",
    "satisfaction",
    "surprise",
]

ENDING_TYPES = [
    "",
    "question",
    "reveal",
    "loop",
    "call_to_action",
    "punchline",
    "cliffhanger",
    "summary",
]

VOICE_TYPES = ["", "no_voice", "human_voice", "ai_voice", "uncertain"]

VOICE_STYLES = [
    "",
    "energetic_fast",
    "calm",
    "dramatic",
    "comedic",
    "serious",
    "whisper",
    "character_voice",
]

CAPTION_STYLES = [
    "",
    "large_center",
    "word_by_word",
    "sentence_bottom",
    "karaoke_highlight",
    "minimal",
    "none",
]

MEME_USAGE = [
    "",
    "none",
    "reaction_image",
    "meme_template",
    "emoji",
    "gif_insert",
    "multiple_memes",
]

SOUND_USAGE = [
    "",
    "none",
    "background_music",
    "isolated_sfx",
    "meme_soundboard",
    "voice_options",
    "mixed",
]

TIMELINE_EVENT_TYPES = [
    "hook",
    "caption",
    "meme_insert",
    "image_insert",
    "sound_effect",
    "voiceover",
    "zoom",
    "camera_shake",
    "transition",
    "reveal",
    "cta",
    "other",
]


def register_analysis_review_routes(app, page, esc) -> None:
    def options(values, current):
        return "".join(
            f'<option value="{esc(value)}"'
            f'{" selected" if str(value) == str(current or "") else ""}>'
            f'{esc(value or "—")}</option>'
            for value in values
        )

    @app.route("/analysis-review")
    def analysis_review_index():
        runs = [
            item
            for item in list_reference_runs(limit=500)
            if str(item.get("status")) == "ANALYZED"
        ]

        rows = "".join(
            f"""
            <tr>
              <td>{esc(item.get("source_name", ""))}</td>
              <td>{esc(item.get("detected_format", ""))}</td>
              <td>{esc(item.get("confidence", 0))}%</td>
              <td>
                <a class="btn"
                   href="/analysis-review/{esc(Path(item.get('source_name', '')).name)}">
                  Review analysis
                </a>
              </td>
            </tr>
            """
            for item in runs
        ) or '<tr><td colspan="4">No analyzed references yet.</td></tr>'

        stats = get_learning_stats()
        stats_rows = "".join(
            f"""
            <tr>
              <td>{esc(item.get("label_group", ""))}</td>
              <td>{esc(item.get("label_value", ""))}</td>
              <td>{esc(item.get("corrected_count", 0))}</td>
            </tr>
            """
            for item in stats
        ) or '<tr><td colspan="3">No human corrections yet.</td></tr>'

        body = f"""
        <h1>Analysis Review</h1>
        <div class="card">
          <p>
            Correct the analysis, then create a Creator AI project from the
            corrected production plan.
          </p>
        </div>
        <div class="card">
          <table>
            <thead>
              <tr><th>Reference</th><th>AI format</th><th>Confidence</th><th></th></tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>
        </div>
        <h2>Learning from corrections</h2>
        <div class="card">
          <table>
            <thead><tr><th>Group</th><th>Label</th><th>Examples</th></tr></thead>
            <tbody>{stats_rows}</tbody>
          </table>
        </div>
        """
        return page("Analysis Review", body, "/analysis-review")

    @app.route("/analysis-review/<path:source_name>")
    def analysis_review_detail(source_name: str):
        source_name = Path(source_name).name
        bundle = load_review_bundle(source_name)
        analysis = bundle["analysis"]
        plan = bundle["plan"]
        correction = bundle["correction"]
        source_key = bundle["source_key"]

        scenes = analysis.get("scenes", [])
        audio_events = analysis.get("audio_events", [])

        scene_rows = "".join(
            f"""
            <tr>
              <td>{esc(scene.get("start", 0))}</td>
              <td>{esc(scene.get("end", 0))}</td>
              <td>{esc(scene.get("motion_score", 0))}</td>
              <td>{esc(scene.get("text_density", 0))}</td>
              <td>{esc(scene.get("insert_probability", 0))}</td>
            </tr>
            """
            for scene in scenes[:200]
        ) or '<tr><td colspan="5">No scenes found.</td></tr>'

        audio_rows = "".join(
            f"""
            <tr>
              <td>{esc(event.get("start", 0))}</td>
              <td>{esc(event.get("end", 0))}</td>
              <td>{esc(event.get("kind", ""))}</td>
              <td>{esc(event.get("peak_db", 0))}</td>
            </tr>
            """
            for event in audio_events[:200]
        ) or '<tr><td colspan="4">No audio events found.</td></tr>'

        timeline_rows = "".join(
            f"""
            <tr>
              <td>{esc(item.get("start_time", 0))}</td>
              <td>{esc(item.get("end_time", 0))}</td>
              <td>{esc(item.get("event_type", ""))}</td>
              <td>{esc(item.get("label", ""))}</td>
              <td>{esc(item.get("notes", ""))}</td>
              <td>
                <form method="post"
                      action="/analysis-review/timeline/delete/{esc(item.get('id'))}">
                  <input type="hidden" name="source_name" value="{esc(source_name)}">
                  <button type="submit">Delete</button>
                </form>
              </td>
            </tr>
            """
            for item in bundle["timeline_corrections"]
        ) or '<tr><td colspan="6">No corrected timeline events yet.</td></tr>'

        original_format = plan.get("detected_format", "")
        corrected_format = (
            correction.get("corrected_format")
            or original_format
            or "manual_complex_edit"
        )

        body = f"""
        <h1>Review: {esc(source_name)}</h1>

        <div class="card">
          <p>
            <b>AI format:</b> {esc(original_format)}
            · <b>Confidence:</b> {esc(plan.get("confidence", 0))}%
            · <b>Voiceover likely:</b>
              {esc(analysis.get("probable_voiceover", False))}
            · <b>AI voice likelihood:</b>
              {esc(analysis.get("synthetic_voice_confidence", 0))}%
          </p>
        </div>

        <form method="post" action="/analysis-review/save/{esc(source_key)}">
          <input type="hidden" name="source_name" value="{esc(source_name)}">
          <input type="hidden" name="original_format" value="{esc(original_format)}">

          <div class="card">
            <h2>Correct overall understanding</h2>

            <label>Correct format</label>
            <select name="corrected_format">
              {options(FORMATS, corrected_format)}
            </select>

            <label>Hook type</label>
            <select name="hook_type">
              {options(HOOK_TYPES, correction.get("hook_type"))}
            </select>

            <label>Video goal</label>
            <select name="video_goal">
              {options(VIDEO_GOALS, correction.get("video_goal"))}
            </select>

            <label>Main emotion</label>
            <select name="emotion">
              {options(EMOTIONS, correction.get("emotion"))}
            </select>

            <label>Ending type</label>
            <select name="ending_type">
              {options(ENDING_TYPES, correction.get("ending_type"))}
            </select>

            <label>Voice type</label>
            <select name="voice_type">
              {options(VOICE_TYPES, correction.get("voice_type"))}
            </select>

            <label>Voice style</label>
            <select name="voice_style">
              {options(VOICE_STYLES, correction.get("voice_style"))}
            </select>

            <label>Caption style</label>
            <select name="caption_style">
              {options(CAPTION_STYLES, correction.get("caption_style"))}
            </select>

            <label>Meme usage</label>
            <select name="meme_usage">
              {options(MEME_USAGE, correction.get("meme_usage"))}
            </select>

            <label>Sound usage</label>
            <select name="sound_usage">
              {options(SOUND_USAGE, correction.get("sound_usage"))}
            </select>

            <label>Notes</label>
            <textarea name="notes" rows="4">{esc(correction.get("notes", ""))}</textarea>

            <button type="submit">Save correction and rebuild plan</button>
          </div>
        </form>

        <div class="card">
          <h2>Create from this analysis</h2>
          <p>
            This reads the corrected plan, selects matching gameplay, uses
            sounds only when the format requires them, and creates a Creator AI
            project. Unsupported narrated formats are kept in Needs Assets
            instead of being incorrectly rendered as soundboard videos.
          </p>
          <form method="post"
                action="/analysis-review/create-project/{esc(source_key)}">
            <input type="hidden" name="source_name" value="{esc(source_name)}">
            <button type="submit">Create project from analysis</button>
          </form>
        </div>

        <div class="card">
          <h2>Add corrected timeline event</h2>
          <form method="post"
                action="/analysis-review/timeline/add/{esc(source_key)}">
            <input type="hidden" name="source_name" value="{esc(source_name)}">
            <input name="start_time" type="number" step="0.01" min="0"
                   placeholder="Start" required>
            <input name="end_time" type="number" step="0.01" min="0"
                   placeholder="End" required>
            <select name="event_type">
              {options(TIMELINE_EVENT_TYPES, "")}
            </select>
            <input name="label"
                   placeholder="e.g. Vine boom / image insert / hook text">
            <input name="notes" placeholder="Optional correction note">
            <button type="submit">Add event</button>
          </form>
        </div>

        <div class="card">
          <h2>Human-corrected timeline</h2>
          <table>
            <thead>
              <tr><th>Start</th><th>End</th><th>Type</th><th>Label</th><th>Notes</th><th></th></tr>
            </thead>
            <tbody>{timeline_rows}</tbody>
          </table>
        </div>

        <div class="card">
          <h2>AI scene detection</h2>
          <table>
            <thead>
              <tr><th>Start</th><th>End</th><th>Motion</th><th>Text</th><th>Insert</th></tr>
            </thead>
            <tbody>{scene_rows}</tbody>
          </table>
        </div>

        <div class="card">
          <h2>AI audio events</h2>
          <table>
            <thead>
              <tr><th>Start</th><th>End</th><th>Type</th><th>Peak dB</th></tr>
            </thead>
            <tbody>{audio_rows}</tbody>
          </table>
        </div>
        """
        return page("Review Analysis", body, "/analysis-review")

    @app.route("/analysis-review/save/<source_key>", methods=["POST"])
    def analysis_review_save(source_key: str):
        source_name = str(request.form.get("source_name") or source_key)
        save_analysis_correction(
            source_key=source_key,
            source_name=source_name,
            original_format=str(request.form.get("original_format") or ""),
            corrected_format=str(request.form.get("corrected_format") or ""),
            hook_type=str(request.form.get("hook_type") or ""),
            video_goal=str(request.form.get("video_goal") or ""),
            emotion=str(request.form.get("emotion") or ""),
            ending_type=str(request.form.get("ending_type") or ""),
            voice_type=str(request.form.get("voice_type") or ""),
            voice_style=str(request.form.get("voice_style") or ""),
            caption_style=str(request.form.get("caption_style") or ""),
            meme_usage=str(request.form.get("meme_usage") or ""),
            sound_usage=str(request.form.get("sound_usage") or ""),
            notes=str(request.form.get("notes") or ""),
        )
        write_corrected_bundle(source_name)
        return redirect(f"/analysis-review/{Path(source_name).name}")

    @app.route(
        "/analysis-review/create-project/<source_key>",
        methods=["POST"],
    )
    def analysis_create_project(source_key: str):
        source_name = str(request.form.get("source_name") or source_key)
        try:
            # Ensure the current human selections are reflected in the plan.
            write_corrected_bundle(source_name)
            project = create_project_from_analysis(
                source_name,
                fetch_sounds=True,
            )
        except Exception as exc:
            return page(
                "Creator project error",
                f"""
                <h1>Could not create project</h1>
                <div class="card"><pre>{esc(exc)}</pre></div>
                <p><a class="btn"
                      href="/analysis-review/{esc(Path(source_name).name)}">
                   Back to analysis
                </a></p>
                """,
                "/analysis-review",
            ), 500

        return redirect(f"/creator-ai/project/{project.video_id}")

    @app.route(
        "/analysis-review/timeline/add/<source_key>",
        methods=["POST"],
    )
    def analysis_timeline_add(source_key: str):
        source_name = str(request.form.get("source_name") or source_key)
        add_timeline_correction(
            source_key=source_key,
            start_time=float(request.form.get("start_time") or 0),
            end_time=float(request.form.get("end_time") or 0),
            event_type=str(request.form.get("event_type") or "other"),
            label=str(request.form.get("label") or ""),
            notes=str(request.form.get("notes") or ""),
        )
        write_corrected_bundle(source_name)
        return redirect(f"/analysis-review/{Path(source_name).name}")

    @app.route(
        "/analysis-review/timeline/delete/<int:correction_id>",
        methods=["POST"],
    )
    def analysis_timeline_delete(correction_id: int):
        source_name = str(request.form.get("source_name") or "")
        delete_timeline_correction(correction_id)
        if source_name:
            write_corrected_bundle(source_name)
        return redirect(
            f"/analysis-review/{Path(source_name).name}"
            if source_name
            else "/analysis-review"
        )