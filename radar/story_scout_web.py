from __future__ import annotations

from flask import request

from .story_scout import (
    import_downloaded_reference,
    list_candidates,
    scan_storytelling_shorts,
    scout_stats,
    update_status,
)


def _number(value: int | float) -> str:
    value = float(value or 0)
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{int(value)}"


def register_story_scout_routes(app, page, esc) -> None:
    @app.route("/story-scout")
    def story_scout_home():
        selected_status = str(
            request.args.get("status") or ""
        ).upper()
        candidates = list_candidates(
            status=selected_status,
            limit=300,
        )
        stats = scout_stats()

        cards = []
        for item in candidates:
            reasons = "".join(
                f"<li>{esc(reason)}</li>"
                for reason in item.reasons[:6]
            )
            review_actions = ""
            if item.status not in {"APPROVED", "IMPORTED"}:
                review_actions += f"""
                <form method="post"
                      action="/story-scout/status"
                      style="display:inline-block;margin-right:6px">
                  <input type="hidden"
                         name="video_id"
                         value="{esc(item.video_id)}">
                  <input type="hidden"
                         name="status"
                         value="APPROVED">
                  <button type="submit">Approve Reference</button>
                </form>
                """
            if item.status != "REJECTED":
                review_actions += f"""
                <form method="post"
                      action="/story-scout/status"
                      style="display:inline-block">
                  <input type="hidden"
                         name="video_id"
                         value="{esc(item.video_id)}">
                  <input type="hidden"
                         name="status"
                         value="REJECTED">
                  <button type="submit">Reject</button>
                </form>
                """

            import_form = ""
            if item.status in {"APPROVED", "DOWNLOADED", "IMPORTED"}:
                import_form = f"""
                <div style="margin-top:12px;padding-top:12px;border-top:1px solid #263247">
                  <p>
                    Download the approved Short yourself, then upload the file
                    here so the Story Analyzer can learn from it.
                  </p>
                  <form method="post"
                        action="/story-scout/import"
                        enctype="multipart/form-data">
                    <input type="hidden"
                           name="video_id"
                           value="{esc(item.video_id)}">
                    <input type="file"
                           name="reference_file"
                           accept=".mp4,.mov,.mkv,.webm"
                           required>
                    <input type="text"
                           name="notes"
                           placeholder="Why this reference is good"
                           style="width:100%;margin:8px 0">
                    <button type="submit">
                      Import Downloaded Reference
                    </button>
                  </form>
                </div>
                """

            cards.append(
                f"""
                <div class="card">
                  <div class="grid" style="grid-template-columns:220px 1fr">
                    <div>
                      <img src="{esc(item.thumbnail_url)}"
                           style="width:100%;border-radius:8px">
                    </div>
                    <div>
                      <h3>{esc(item.title)}</h3>
                      <p>
                        <b>{esc(item.channel_title)}</b>
                        · {esc(item.duration_seconds)}s
                        · {esc(_number(item.view_count))} views
                        · {esc(_number(item.views_per_day))}/day
                      </p>
                      <p>
                        <b>Status:</b> {esc(item.status)}
                        · <b>Opportunity:</b> {esc(item.opportunity_score)}
                        · <b>Viral:</b> {esc(item.viral_score)}
                        · <b>Story:</b> {esc(item.storytelling_score)}
                        · <b>Gaming:</b> {esc(item.gaming_background_score)} · <b>English:</b> {esc(item.english_confidence)}% · <b>Game:</b> {esc(item.detected_game or 'unknown')}
                      </p>
                      <p>
                        Engagement: {esc(item.engagement_rate)}%
                        · Views/subscribers: {esc(item.views_to_subs)}×
                      </p>
                      <ul>{reasons}</ul>
                      <a class="btn"
                         href="{esc(item.url)}"
                         target="_blank"
                         rel="noopener">
                        Open YouTube Short
                      </a>
                      <span style="margin-left:8px">{review_actions}</span>
                      {import_form}
                    </div>
                  </div>
                </div>
                """
            )

        body = f"""
        <h1>English Roblox &amp; Minecraft Story Scout</h1>

        <div class="grid">
          <div class="card">
            <div class="score">{esc(stats["new"])}</div>
            <p>Awaiting review</p>
          </div>
          <div class="card">
            <div class="score">{esc(stats["approved"])}</div>
            <p>Approved</p>
          </div>
          <div class="card">
            <div class="score">{esc(stats["imported"])}</div>
            <p>Imported for learning</p>
          </div>
        </div>

        <div class="card">
          <h2>Find current viral storytelling Shorts</h2>
          <p>
            Searches only English storytelling Shorts using Roblox or Minecraft background gameplay. Results are filtered twice: YouTube relevance language plus a local English-language and game-specific check.
          </p>
          <form method="post" action="/story-scout/scan">
            <div class="grid">
              <p>
                <label>Published within</label><br>
                <input type="number"
                       name="days_back"
                       value="30"
                       min="1"
                       max="365">
              </p>
              <p>
                <label>Minimum views</label><br>
                <input type="number"
                       name="min_views"
                       value="100000"
                       min="1000">
              </p>
              <p>
                <label>Region</label><br>
                <input name="region"
                       value="US"
                       maxlength="2">
              </p>
              <p>
                <label>Search queries this run</label><br>
                <input type="number"
                       name="max_queries"
                       value="4"
                       min="1"
                       max="6">
              </p>
            </div>
            <p>
              <label>Optional custom query</label><br>
              <input name="custom_query"
                     placeholder="e.g. scary minecraft parkour storytime english"
                     style="width:100%">
            </p>
            <button type="submit">
              Scan Viral Gaming Story Shorts
            </button>
          </form>
        </div>

        <div class="card">
          <a class="btn" href="/story-scout">All</a>
          <a class="btn" href="/story-scout?status=NEW">Needs Review</a>
          <a class="btn" href="/story-scout?status=APPROVED">Approved</a>
          <a class="btn" href="/story-scout?status=IMPORTED">Imported</a>
          <a class="btn" href="/story-scout?status=REJECTED">Rejected</a>
        </div>

        {"".join(cards) or '<div class="card">No candidates found yet.</div>'}
        """
        return page(
            "Viral Gaming Story Scout",
            body,
            "/story-scout",
        )

    @app.route("/story-scout/scan", methods=["POST"])
    def story_scout_scan():
        try:
            scan_storytelling_shorts(
                days_back=int(
                    request.form.get("days_back") or 30
                ),
                region=str(
                    request.form.get("region") or "US"
                ).upper(),
                min_views=int(
                    request.form.get("min_views") or 100000
                ),
                max_queries=int(
                    request.form.get("max_queries") or 4
                ),
                custom_query=str(
                    request.form.get("custom_query") or ""
                ),
            )
        except Exception as exc:
            return page(
                "Story scan failed",
                f"""
                <h1>Story scan failed</h1>
                <div class="card"><pre>{esc(exc)}</pre></div>
                <a class="btn" href="/story-scout">Back</a>
                """,
                "/story-scout",
            ), 500

        return story_scout_home()

    @app.route("/story-scout/status", methods=["POST"])
    def story_scout_status():
        video_id = str(
            request.form.get("video_id") or ""
        ).strip()
        status = str(
            request.form.get("status") or ""
        ).strip().upper()
        try:
            update_status(video_id, status)
        except Exception as exc:
            return page(
                "Review failed",
                f"""
                <h1>Could not update reference</h1>
                <div class="card"><pre>{esc(exc)}</pre></div>
                <a class="btn" href="/story-scout">Back</a>
                """,
                "/story-scout",
            ), 400
        return story_scout_home()

    @app.route("/story-scout/import", methods=["POST"])
    def story_scout_import():
        video_id = str(
            request.form.get("video_id") or ""
        ).strip()
        uploaded = request.files.get("reference_file")
        if uploaded is None:
            return "No reference file selected.", 400

        try:
            import_downloaded_reference(
                video_id=video_id,
                uploaded_file=uploaded,
                notes=str(request.form.get("notes") or ""),
            )
        except Exception as exc:
            return page(
                "Reference import failed",
                f"""
                <h1>Reference import failed</h1>
                <div class="card"><pre>{esc(exc)}</pre></div>
                <a class="btn" href="/story-scout">Back</a>
                """,
                "/story-scout",
            ), 400

        return page(
            "Reference imported",
            """
            <h1>Story reference imported</h1>
            <div class="card">
              <p>
                The local video and its discovery metrics are now saved in the
                Story Reference Library and marked ready for Story Analysis.
              </p>
            </div>
            <a class="btn" href="/story-scout?status=IMPORTED">
              View imported references
            </a>
            """,
            "/story-scout",
        )
