from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from flask import redirect, request

from .classification_feedback import list_feedback, save_feedback
from .video_intelligence import CONTENT_TYPES, PRIMARY_FORMATS, classify_video


def register_classification_routes(app, base: Path, page, esc, load_recommendations):
    def _load_candidates() -> pd.DataFrame:
        df = load_recommendations()
        return df.fillna("") if not df.empty else df

    @app.route("/classification-review")
    def classification_review():
        df = _load_candidates()
        if df.empty:
            return page(
                "Classification Review",
                '<h1>Classification Review</h1><div class="card"><p>No candidates found. Run the scanner first.</p></div>',
                "/classification-review",
            )

        if "classification_confidence" in df.columns:
            df["_conf"] = pd.to_numeric(df["classification_confidence"], errors="coerce").fillna(0)
            df = df.sort_values(["classification_needs_review", "_conf"], ascending=[False, True])

        cards = []
        for _, row in df.head(250).iterrows():
            video = row.to_dict()
            result = classify_video(video)
            labels = "".join(
                f'<option value="{esc(label)}" {"selected" if label == result.primary_format else ""}>{esc(label)}</option>'
                for label in PRIMARY_FORMATS
            )
            content_options = "".join(
                f'<option value="{esc(label)}" {"selected" if label == result.content_type else ""}>{esc(label)}</option>'
                for label in CONTENT_TYPES
            )
            evidence = "<br>".join(esc(x) for x in result.evidence)
            status = "REVIEW" if result.needs_review else "OK"
            status_cls = "warn" if result.needs_review else "good"
            cards.append(f'''
            <div class="card">
              <div class="section-title"><h3>{esc(video.get("title", ""))}</h3><span class="{status_cls}">{status}</span></div>
              <p><b>AI label:</b> {esc(result.primary_format)} · <b>Confidence:</b> {result.confidence}% · <b>Content:</b> {esc(result.content_type)}</p>
              <p><b>Secondary:</b> {esc(", ".join(result.secondary_formats) or "None")}</p>
              <p><b>Evidence:</b><br>{evidence}</p>
              <form method="post" action="/classification-review/save/{esc(video.get("video_id", ""))}">
                <input type="hidden" name="ai_label" value="{esc(result.primary_format)}">
                <label>Correct format</label>
                <select name="correct_label">{labels}</select>
                <label>Content type</label>
                <select name="content_type">{content_options}</select>
                <input name="reason" placeholder="Optional reason: title misleading, actually an animation...">
                <button>Save correction</button>
                <a class="btn" target="_blank" href="{esc(video.get("url", ""))}">Open video</a>
              </form>
            </div>
            ''')

        feedback_rows = list_feedback()
        summary = "".join(
            f'<tr><td>{esc(x.get("video_id"))}</td><td>{esc(x.get("ai_label"))}</td><td>{esc(x.get("correct_label"))}</td><td>{esc(x.get("reason"))}</td></tr>'
            for x in feedback_rows[:100]
        ) or '<tr><td colspan="4">No corrections saved yet.</td></tr>'

        body = f'''
        <h1>Classification Review</h1>
        <div class="card">
          <p>Low-confidence and ambiguous videos appear first. Corrections are stored in <code>outputs/video_classification.db</code> and override future scans.</p>
        </div>
        {"".join(cards)}
        <div class="card"><h2>Saved corrections</h2><table><thead><tr><th>Video</th><th>AI</th><th>Correct</th><th>Reason</th></tr></thead><tbody>{summary}</tbody></table></div>
        '''
        return page("Classification Review", body, "/classification-review")

    @app.route("/classification-review/save/<video_id>", methods=["POST"])
    def classification_save(video_id: str):
        save_feedback(
            video_id=video_id,
            ai_label=str(request.form.get("ai_label") or "manual_review"),
            correct_label=str(request.form.get("correct_label") or "manual_review"),
            content_type=str(request.form.get("content_type") or "unknown"),
            reason=str(request.form.get("reason") or "").strip(),
        )
        return redirect("/classification-review")
