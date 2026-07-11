from __future__ import annotations

import json
from pathlib import Path

from flask import redirect, request

from .reference_library import (
    ANALYZED_DIR,
    FAILED_DIR,
    PENDING_DIR,
    REPORT_DIR,
    analyze_pending_references,
    list_reference_runs,
)
from .reference_scout import (
    list_reference_queue,
    set_reference_status,
    update_reference_queue,
)


def register_reference_routes(app, base: Path, page, esc) -> None:
    def count_videos(folder: Path) -> int:
        extensions = {".mp4", ".mov", ".mkv", ".webm"}
        if not folder.exists():
            return 0
        return sum(
            1
            for path in folder.rglob("*")
            if path.is_file() and path.suffix.lower() in extensions
        )

    def status_badge(status: str) -> str:
        normalized = str(status or "").upper()
        if normalized in {"FULLY_ANALYZED", "ANALYZED", "APPROVED"}:
            css = "good"
        elif normalized in {
            "DISCOVERED",
            "MEDIA_NEEDED",
            "METADATA_ANALYZED",
            "ANALYZING",
        }:
            css = "warn"
        else:
            css = "bad"
        return f'<span class="{css}">{esc(normalized)}</span>'

    @app.route("/reference-queue")
    def reference_queue_page():
        status_filter = str(request.args.get("status") or "").strip().upper()
        queue = list_reference_queue(
            status=status_filter or None,
            limit=1000,
        )
        runs = list_reference_runs(limit=200)

        pending_count = count_videos(PENDING_DIR)
        analyzed_count = count_videos(ANALYZED_DIR)
        failed_count = count_videos(FAILED_DIR)

        cards = []
        for item in queue:
            reasons = "<br>".join(
                f"✓ {esc(reason)}"
                for reason in item.get("reasons", [])
            ) or "No reasons recorded."

            video_id = str(item.get("video_id") or "")
            current_status = str(item.get("status") or "DISCOVERED")
            url = str(item.get("url") or "#")

            buttons = f"""
            <form method="post"
                  action="/reference-queue/status/{esc(video_id)}"
                  style="display:inline">
              <input type="hidden" name="status" value="APPROVED">
              <button type="submit">Approve</button>
            </form>
            <form method="post"
                  action="/reference-queue/status/{esc(video_id)}"
                  style="display:inline">
              <input type="hidden" name="status" value="MEDIA_NEEDED">
              <button type="submit">Need media</button>
            </form>
            <form method="post"
                  action="/reference-queue/status/{esc(video_id)}"
                  style="display:inline">
              <input type="hidden" name="status" value="REJECTED">
              <button type="submit">Reject</button>
            </form>
            """

            cards.append(
                f"""
                <div class="card">
                  <div class="section-title">
                    <h3>{esc(item.get("title", ""))}</h3>
                    {status_badge(current_status)}
                  </div>
                  <p>
                    <b>Learning value:</b> {esc(item.get("learning_value", 0))}
                    · <b>Format:</b> {esc(item.get("primary_format", ""))}
                    · <b>Confidence:</b>
                      {esc(item.get("classification_confidence", 0))}%
                  </p>
                  <p>
                    <b>Views:</b> {esc(item.get("view_count", 0))}
                    · <b>Subscribers:</b>
                      {esc(item.get("subscriber_count", 0))}
                    · <b>Age:</b> {esc(item.get("age_days", 0))} days
                  </p>
                  <p><b>Why selected:</b><br>{reasons}</p>
                  <div class="row-actions">
                    <a class="btn" target="_blank" href="{esc(url)}">
                      Open video
                    </a>
                    {buttons}
                  </div>
                </div>
                """
            )

        if not cards:
            cards.append(
                """
                <div class="card">
                  <p class="muted">
                    No reference candidates found for this filter.
                  </p>
                </div>
                """
            )

        run_rows = []
        for item in runs:
            report_path = str(item.get("report_path") or "")
            report_link = ""
            if report_path:
                report_name = Path(report_path).name
                report_link = (
                    f'<a href="/reference-reports/{esc(report_name)}">'
                    "Open report</a>"
                )

            run_rows.append(
                f"""
                <tr>
                  <td>{esc(item.get("source_name", ""))}</td>
                  <td>{status_badge(item.get("status", ""))}</td>
                  <td>{esc(item.get("detected_format", ""))}</td>
                  <td>{esc(item.get("confidence", 0))}%</td>
                  <td>{report_link}</td>
                  <td>{esc(item.get("error_message", ""))}</td>
                </tr>
                """
            )

        filters = " ".join(
            f'<a class="btn" href="/reference-queue'
            f'{("?status=" + status) if status else ""}">'
            f'{label}</a>'
            for status, label in [
                ("", "All"),
                ("DISCOVERED", "Discovered"),
                ("APPROVED", "Approved"),
                ("MEDIA_NEEDED", "Media needed"),
                ("FULLY_ANALYZED", "Fully analyzed"),
                ("REJECTED", "Rejected"),
            ]
        )

        body = f"""
        <h1>Reference Queue</h1>

        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-value">{len(queue)}</div>
            <div class="stat-label">Queue items shown</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{pending_count}</div>
            <div class="stat-label">Pending files</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{analyzed_count}</div>
            <div class="stat-label">Analyzed files</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{failed_count}</div>
            <div class="stat-label">Failed files</div>
          </div>
        </div>

        <div class="card">
          <p>
            Reference Scout chooses the most useful viral videos to learn from.
            Full frame/audio analysis starts only when a permitted local file is
            added to <code>assets/reference_videos/pending/</code>.
          </p>
          <div class="row-actions">
            <form method="post" action="/reference-queue/refresh">
              <label>Scout limit</label>
              <input name="limit" type="number" value="25" min="1" max="250">
              <button type="submit">Refresh from Trend Radar</button>
            </form>

            <form method="post" action="/reference-queue/analyze-pending">
              <label>Sample every</label>
              <input name="sample_every" type="number"
                     value="0.5" min="0.2" max="5" step="0.1">
              <button type="submit">Analyze all pending files</button>
            </form>
          </div>
          <p>
            <b>Pending folder:</b>
            <span class="path">{esc(PENDING_DIR)}</span>
          </p>
        </div>

        <div class="card">
          <div class="row-actions">{filters}</div>
        </div>

        <h2>Learning candidates</h2>
        {"".join(cards)}

        <h2>Full-analysis history</h2>
        <div class="card">
          <table>
            <thead>
              <tr>
                <th>File</th>
                <th>Status</th>
                <th>Detected format</th>
                <th>Confidence</th>
                <th>Report</th>
                <th>Error</th>
              </tr>
            </thead>
            <tbody>
              {"".join(run_rows) or '<tr><td colspan="6">No runs yet.</td></tr>'}
            </tbody>
          </table>
        </div>
        """
        return page(
            "Reference Queue",
            body,
            "/reference-queue",
        )

    @app.route("/reference-queue/refresh", methods=["POST"])
    def reference_queue_refresh():
        try:
            limit = max(
                1,
                min(
                    250,
                    int(request.form.get("limit") or 25),
                ),
            )
            update_reference_queue(limit=limit)
        except Exception as exc:
            return page(
                "Reference queue error",
                f"""
                <h1>Reference Scout failed</h1>
                <div class="card"><pre>{esc(exc)}</pre></div>
                """,
                "/reference-queue",
            ), 500

        return redirect("/reference-queue")

    @app.route(
        "/reference-queue/status/<video_id>",
        methods=["POST"],
    )
    def reference_queue_status(video_id: str):
        try:
            set_reference_status(
                video_id,
                str(request.form.get("status") or "DISCOVERED"),
            )
        except Exception as exc:
            return page(
                "Reference status error",
                f"""
                <h1>Status update failed</h1>
                <div class="card"><pre>{esc(exc)}</pre></div>
                """,
                "/reference-queue",
            ), 500

        return redirect("/reference-queue")

    @app.route(
        "/reference-queue/analyze-pending",
        methods=["POST"],
    )
    def reference_queue_analyze_pending():
        try:
            sample_every = max(
                0.2,
                min(
                    5.0,
                    float(request.form.get("sample_every") or 0.5),
                ),
            )
            results = analyze_pending_references(
                sample_interval=sample_every,
                move_after=True,
            )
        except Exception as exc:
            return page(
                "Reference analysis error",
                f"""
                <h1>Batch analysis failed</h1>
                <div class="card"><pre>{esc(exc)}</pre></div>
                """,
                "/reference-queue",
            ), 500

        analyzed = sum(
            1 for item in results if item.get("status") == "ANALYZED"
        )
        failed = sum(
            1 for item in results if item.get("status") == "FAILED"
        )

        return redirect(
            f"/reference-queue?batch_analyzed={analyzed}&batch_failed={failed}"
        )

    @app.route("/reference-reports/<name>")
    def reference_report_file(name: str):
        safe_name = Path(name).name
        path = REPORT_DIR / safe_name
        if not path.exists():
            return "Reference report not found", 404

        if path.suffix.lower() == ".md":
            text = path.read_text(encoding="utf-8")
            return page(
                safe_name,
                f"""
                <h1>{esc(safe_name)}</h1>
                <div class="card">
                  <pre style="white-space:pre-wrap">{esc(text)}</pre>
                </div>
                """,
                "/reference-queue",
            )

        return path.read_text(encoding="utf-8"), 200, {
            "Content-Type": "application/json; charset=utf-8"
        }
