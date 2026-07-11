from __future__ import annotations

from flask import redirect

from .channel_feedback import (
    SYNC_HOURS,
    last_sync_age_hours,
    load_channel_rows,
    load_learning,
    sync_if_stale,
)


def register_channel_routes(app, page, esc):
    @app.route('/my-channel')
    def my_channel_page():
        rows = load_channel_rows(100)
        learning = load_learning()
        age = last_sync_age_hours()

        template_rows = ''.join(
            '<tr>'
            f'<td>{esc(name)}</td>'
            f'<td>{int(data.get("videos", 0))}</td>'
            f'<td>{float(data.get("avg_views", 0)):,.0f}</td>'
            f'<td>{float(data.get("avg_views_per_hour", 0)):,.1f}</td>'
            f'<td>{float(data.get("personal_multiplier", 1)):.2f}×</td>'
            '</tr>'
            for name, data in sorted(
                learning.get('templates', {}).items(),
                key=lambda item: item[1].get('personal_multiplier', 1),
                reverse=True,
            )
        ) or '<tr><td colspan="5" class="muted">No learning data yet.</td></tr>'

        video_rows = ''.join(
            '<tr>'
            f'<td><a target="_blank" href="{esc(v["url"])}">{esc(v["title"])}</a></td>'
            f'<td>{int(v["view_count"]):,}</td>'
            f'<td>{float(v["views_per_hour"]):,.1f}</td>'
            f'<td>{float(v["like_rate"]) * 100:.2f}%</td>'
            f'<td>{esc(v["template_type"])}</td>'
            f'<td>{esc(v["hook_type"])}</td>'
            '</tr>'
            for v in rows
        ) or '<tr><td colspan="6" class="muted">Waiting for the first automatic sync.</td></tr>'

        last_sync = 'never' if age is None else f'{age:.1f} hours ago'
        body = f'''
        <h1>📈 My Channel Learning</h1>
        <div class="card">
          <div class="section-title">
            <div>
              <h3>Automatic feedback</h3>
              <p class="muted">Public views, likes and comments sync every {SYNC_HOURS} hours.</p>
            </div>
            <form method="post" action="/my-channel/sync"><button>Sync now</button></form>
          </div>
          <p><b>Last sync:</b> {last_sync}</p>
        </div>
        <div class="card">
          <h2>What works best for your channel</h2>
          <table><thead><tr><th>Format</th><th>Videos</th><th>Avg views</th><th>Avg views/hour</th><th>AI multiplier</th></tr></thead>
          <tbody>{template_rows}</tbody></table>
        </div>
        <div class="card">
          <h2>Latest uploads</h2>
          <table><thead><tr><th>Video</th><th>Views</th><th>Views/hour</th><th>Like rate</th><th>Format</th><th>Hook</th></tr></thead>
          <tbody>{video_rows}</tbody></table>
        </div>
        <div class="card"><p class="muted">An API key only exposes public statistics. Stayed to watch, average percentage viewed, subscriber gain per video and retention require YouTube Analytics OAuth.</p></div>
        '''
        return page('My Channel', body, '/my-channel')

    @app.route('/my-channel/sync', methods=['POST'])
    def my_channel_sync():
        try:
            sync_if_stale(force=True)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            return page(
                'Channel sync error',
                f'<h1>Sync failed</h1><div class="card"><pre>{esc(exc)}</pre></div>',
                '/my-channel',
            ), 500
        return redirect('/my-channel')
