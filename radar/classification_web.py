from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from flask import redirect, request

from .classification_feedback import list_feedback, save_feedback
from .video_intelligence import (
    CONTENT_TYPES,
    PRIMARY_FORMATS,
    classify_video,
)


def register_classification_routes(
    app,
    base: Path,
    page,
    esc,
    load_recommendations,
) -> None:
    def load_candidates() -> pd.DataFrame:
        # trend_report contains both accepted and review candidates.
        trend_report = base / "outputs" / "trend_report.csv"
        if trend_report.exists():
            try:
                return pd.read_csv(trend_report).fillna("")
            except Exception:
                pass
        frame = load_recommendations()
        return frame.fillna("") if not frame.empty else frame

    @app.route("/classification-review")
    def classification_review():
        frame = load_candidates()
        if frame.empty:
            return page(
                "Classification Review",
                """
                <h1>Classification Review</h1>
                <div class="card">
                  <p>No candidates found. Run <code>py trend_radar.py</code> first.</p>
                </div>
                """,
                "/classification-review",
            )

        cards: list[str] = []
        review_rows: list[tuple[int, dict, object]] = []

        for _, row in frame.iterrows():
            video = row.to_dict()
            result = classify_video(video)
            priority = 0 if result.needs_review else 1
            review_rows.append((priority, video, result))

        review_rows.sort(key=lambda item: (item[0], item[2].confidence))

        for _, video, result in review_rows[:250]:
            labels = "".join(
                f'<option value="{esc(label)}"'
                f'{" selected" if label == result.primary_format else ""}>'
                f'{esc(label)}</option>'
                for label in PRIMARY_FORMATS
            )
            content_options = "".join(
                f'<option value="{esc(label)}"'
                f'{" selected" if label == result.content_type else ""}>'
                f'{esc(label)}</option>'
                for label in CONTENT_TYPES
            )
            evidence = "<br>".join(esc(item) for item in result.evidence)
            status = "REVIEW" if result.needs_review else "OK"
            status_class = "warn" if result.needs_review else "good"
            secondary = ", ".join(result.secondary_formats) or "None"
            video_id = str(video.get("video_id") or "")
            url = str(video.get("url") or "#")

            cards.append(
                f"""
                <div class="card">
                  <div class="section-title">
                    <h3>{esc(video.get("title", ""))}</h3>
                    <span class="{status_class}">{status}</span>
                  </div>
                  <p>
                    <b>AI label:</b> {esc(result.primary_format)}
                    · <b>Confidence:</b> {result.confidence}%
                    · <b>Content:</b> {esc(result.content_type)}
                  </p>
                  <p><b>Secondary:</b> {esc(secondary)}</p>
                  <p><b>Evidence:</b><br>{evidence}</p>
                  <form method="post"
                        action="/classification-review/save/{esc(video_id)}">
                    <input type="hidden" name="ai_label"
                           value="{esc(result.primary_format)}">
                    <label>Correct format</label>
                    <select name="correct_label">{labels}</select>
                    <label>Content type</label>
                    <select name="content_type">{content_options}</select>
                    <input name="reason"
                           placeholder="Why was the AI wrong?">
                    <button type="submit">Save correction</button>
                  </form>
                  <p><a target="_blank" href="{esc(url)}">Open video</a></p>
                </div>
                """
            )

        feedback_rows = list_feedback()
        summary = "".join(
            f"<tr>"
            f"<td>{esc(item.get('video_id'))}</td>"
            f"<td>{esc(item.get('ai_label'))}</td>"
            f"<td>{esc(item.get('correct_label'))}</td>"
            f"<td>{esc(item.get('reason'))}</td>"
            f"</tr>"
            for item in feedback_rows[:100]
        ) or '<tr><td colspan="4" class="muted">No corrections saved yet.</td></tr>'

        body = f"""
        <h1>Classification Review</h1>
        <div class="card">
          <p>
            Ambiguous videos appear first. Corrections are stored in
            <code>outputs/video_classification.db</code>.
            After saving corrections, rerun <code>py trend_radar.py</code>
            so corrected videos can enter Creator AI.
          </p>
        </div>
        {"".join(cards)}
        <h2>Saved corrections</h2>
        <div class="card">
          <table>
            <thead>
              <tr><th>Video</th><th>AI</th><th>Correct</th><th>Reason</th></tr>
            </thead>
            <tbody>{summary}</tbody>
          </table>
        </div>
        """
        return page(
            "Classification Review",
            body,
            "/classification-review",
        )

    @app.route(
        "/classification-review/save/<video_id>",
        methods=["POST"],
    )
    def classification_save(video_id: str):
        save_feedback(
            video_id=video_id,
            ai_label=str(request.form.get("ai_label") or "manual_review"),
            correct_label=str(
                request.form.get("correct_label") or "manual_review"
            ),
            content_type=str(request.form.get("content_type") or "unknown"),
            reason=str(request.form.get("reason") or "").strip(),
        )
        return redirect("/classification-review")
