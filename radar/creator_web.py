from __future__ import annotations

from pathlib import Path

from flask import redirect, request, send_file

from .creator_projects import analyze_dataframe, load_project, load_projects
from .sound_library import (
    download_freesound,
    find_replacement_sound,
    load_index,
    preference_for,
    update_sound_feedback,
)
from .template_renderer import render_project
from .clip_brain import save_feedback


def register_creator_routes(app, base: Path, page, render_stats, load_recommendations, esc):
    def asset_by_file(path: str):
        return next((x for x in load_index() if x.file == path), None)

    def project_card(p):
        status_cls = "good" if p.status == "AUTO_READY" else "warn" if p.status in {"READY_FOR_APPROVAL", "NEEDS_ASSETS"} else "bad"
        missing = "<br>".join(esc(x) for x in p.missing) or "None"
        output = f'<a class="btn" href="/creator-ai/draft/{Path(p.output_file).name}">Open draft</a>' if p.output_file else ""
        detail = f'<a class="btn" href="/creator-ai/project/{esc(p.video_id)}">Review project</a>'
        action = ""
        if p.status == "NEEDS_ASSETS" and p.sound_queries:
            action = f'<form method="post" action="/creator-ai/fetch/{esc(p.video_id)}"><button>Find missing sounds</button></form>'
        elif p.status == "AUTO_READY":
            action = f'<form method="post" action="/creator-ai/generate/{esc(p.video_id)}"><button>Generate approved draft</button></form>'
        return f'''
        <div class="card">
          <div class="section-title"><h3>{esc(p.inspiration_title)}</h3><span class="{status_cls}">{esc(p.status)}</span></div>
          <p><b>Template:</b> {esc(p.template_type)} · <b>Confidence:</b> {p.confidence}% · <b>Character:</b> {esc(p.character_name)}</p>
          <p><b>Selected clip:</b> <span class="path">{esc(p.source_clip or 'missing')}</span></p>
          <p><b>Sounds:</b> {len(p.sounds)} · <b>Correct answer:</b> {p.correct_answer}</p>
          <p><b>Missing:</b><br>{missing}</p>
          <div class="row-actions"><a class="btn" target="_blank" href="{esc(p.inspiration_url)}">Inspiration</a>{detail}{action}{output}</div>
        </div>'''

    @app.route("/creator-ai")
    def creator_ai_page():
        projects = load_projects()
        ready = [p for p in projects if p.status == "AUTO_READY"]
        approval = [p for p in projects if p.status == "READY_FOR_APPROVAL"]
        needs = [p for p in projects if p.status == "NEEDS_ASSETS"]
        manual = [p for p in projects if p.status == "MANUAL_ONLY"]
        body = f'''
        <h1>🤖 Creator AI</h1>
        {render_stats("studio")}
        <div class="card">
          <p>The AI prepares a project first. You preview sounds, replace weak ones, choose the correct answer, approve, then render.</p>
          <div class="row-actions">
            <form method="post" action="/creator-ai/analyze"><button>Analyze viral candidates</button></form>
            <form method="post" action="/creator-ai/analyze?fetch=1"><button>Analyze + find sounds</button></form>
          </div>
        </div>
        <h2>Waiting for approval ({len(approval)})</h2>{''.join(project_card(p) for p in approval) or '<div class="card muted">None</div>'}
        <h2>Approved & ready ({len(ready)})</h2>{''.join(project_card(p) for p in ready) or '<div class="card muted">None</div>'}
        <h2>Needs assets ({len(needs)})</h2>{''.join(project_card(p) for p in needs) or '<div class="card muted">None</div>'}
        <h2>Manual only ({len(manual)})</h2>{''.join(project_card(p) for p in manual[:30]) or '<div class="card muted">None</div>'}
        '''
        return page("Creator AI", body, "/creator-ai")

    @app.route("/creator-ai/project/<video_id>")
    def creator_project_page(video_id: str):
        try:
            p = load_project(video_id)
        except Exception as exc:
            return page("Project error", f'<h1>Project not found</h1><pre>{esc(exc)}</pre>', "/creator-ai"), 404

        clip_html = '<p class="muted">No source clip.</p>'
        if p.source_clip:
            clip_html = f'<video controls preload="metadata" src="/creator-ai/source/{esc(Path(p.source_clip).name)}"></video><p class="path">{esc(p.source_clip)}</p>'

        clip_feedback = ""
        if p.source_clip:
            buttons = [
                ("fits", "Fits project"),
                ("does_not_fit", "Doesn't fit"),
                ("wrong_character", "Wrong character"),
                ("wrong_action", "Wrong action"),
                ("character_not_visible", "Character not visible"),
                ("too_much_ui", "Too much UI"),
                ("poor_framing", "Poor framing"),
                ("never_use", "Never use clip"),
            ]
            clip_feedback = '<div class="card"><h3>Clip feedback</h3><p>Teach Clip Brain why this asset fits or fails this specific inspiration.</p><div class="row-actions">' + ''.join(
                f'<form method="post" action="/creator-ai/clip-feedback/{esc(p.video_id)}/{action}"><button>{esc(label)}</button></form>'
                for action, label in buttons
            ) + '</div></div>'

        sound_cards = []
        for idx, sound_file in enumerate(p.sounds):
            asset = asset_by_file(sound_file)
            if not asset:
                continue
            pref = preference_for(asset.asset_id)
            sound_cards.append(f'''
            <div class="card tight">
              <div class="section-title"><h3>Option {idx + 1}: {esc(asset.name)}</h3><span class="muted">Preference {esc(pref.get('rating', 0))}</span></div>
              <audio controls preload="none" src="/sound-library/audio/{esc(asset.asset_id)}" style="width:100%"></audio>
              <p class="small muted">{esc(asset.creator)} · {esc(asset.license)} · {asset.duration:.2f}s · {esc(asset.risk)}</p>
              <div class="row-actions">
                <form method="post" action="/creator-ai/sound-feedback/{esc(video_id)}/{idx}/good"><button>👍 Good</button></form>
                <form method="post" action="/creator-ai/sound-feedback/{esc(video_id)}/{idx}/bad"><button>👎 Bad</button></form>
                <form method="post" action="/creator-ai/sound-feedback/{esc(video_id)}/{idx}/never"><button>🚫 Never use</button></form>
                <form method="post" action="/creator-ai/replace-sound/{esc(video_id)}/{idx}"><button>🔄 Replace</button></form>
                <form method="post" action="/creator-ai/reorder-sound/{esc(video_id)}/{idx}/up"><button>↑</button></form>
                <form method="post" action="/creator-ai/reorder-sound/{esc(video_id)}/{idx}/down"><button>↓</button></form>
              </div>
            </div>''')

        answer_options = ''.join(
            f'<option value="{i}" {"selected" if p.correct_answer == i else ""}>{i}</option>' for i in range(1, max(5, len(p.sounds) + 1))
        )
        clip_options = ''.join(
            f'<option value="{esc(value)}" {"selected" if value == p.source_clip else ""}>{esc(Path(value).name)}</option>'
            for value in (p.source_clips or ([p.source_clip] if p.source_clip else []))
        )
        body = f'''
        <h1>Project Approval</h1>
        <div class="two-col">
          <div>
            <div class="card"><h2>{esc(p.inspiration_title)}</h2>{clip_html}</div>
            <div class="card">
              {clip_feedback}
        <h3>Final settings</h3>
              <form method="post" action="/creator-ai/approve/{esc(video_id)}">
                <label>Source clip</label><br><select name="source_clip" style="max-width:100%">{clip_options}</select><br><br>
                <label>Correct answer</label><br><select name="correct_answer">{answer_options}</select><br><br>
                <label>Approval notes</label><br><input name="approval_notes" value="{esc(p.approval_notes)}" style="width:100%" placeholder="Optional notes"><br><br>
                <button>✅ Approve project</button>
              </form>
              <p class="muted small">Approval is required before rendering. The reveal replays the selected correct sound.</p>
            </div>
          </div>
          <div><h2>Sound choices</h2>{''.join(sound_cards) or '<div class="card">No sounds selected yet.</div>'}</div>
        </div>
        '''
        return page("Project Approval", body, "/creator-ai")

    @app.route("/creator-ai/analyze", methods=["POST"])
    def creator_ai_analyze():
        analyze_dataframe(load_recommendations(), fetch_sounds=request.args.get("fetch") == "1", limit=100)
        return redirect("/creator-ai")

    @app.route("/creator-ai/fetch/<video_id>", methods=["POST"])
    def creator_ai_fetch(video_id: str):
        df = load_recommendations()
        row = df[df["video_id"].astype(str) == str(video_id)] if not df.empty and "video_id" in df.columns else df.iloc[0:0]
        if row.empty:
            return "Video candidate not found", 404
        from .creator_projects import analyze_candidate
        analyze_candidate(row.iloc[0].to_dict(), fetch_sounds=True)
        return redirect(f"/creator-ai/project/{video_id}")

    @app.route("/creator-ai/sound-feedback/<video_id>/<int:index>/<action>", methods=["POST"])
    def creator_sound_feedback(video_id: str, index: int, action: str):
        p = load_project(video_id)
        if index < 0 or index >= len(p.sounds):
            return "Sound index out of range", 400
        asset = asset_by_file(p.sounds[index])
        if asset:
            update_sound_feedback(asset.asset_id, action, p.template_type)
        if action in {"bad", "never"}:
            return redirect(f"/creator-ai/replace-sound/{video_id}/{index}", code=307)
        p.approved = False
        p.status = "READY_FOR_APPROVAL"
        p.save()
        return redirect(f"/creator-ai/project/{video_id}")

    @app.route("/creator-ai/replace-sound/<video_id>/<int:index>", methods=["POST"])
    def creator_replace_sound(video_id: str, index: int):
        p = load_project(video_id)
        if index < 0 or index >= len(p.sounds):
            return "Sound index out of range", 400
        index_items = load_index()
        by_file = {x.file: x for x in index_items}
        excluded = {by_file[x].asset_id for x in p.sounds if x in by_file}
        query = p.sound_queries[index] if index < len(p.sound_queries) else "viral funny meme scream short"
        replacement = find_replacement_sound(query, excluded, p.template_type)
        if not replacement:
            return page("Replacement failed", '<h1>No replacement found</h1><div class="card">Try again later or search the Sound Library manually.</div>', "/creator-ai"), 500
        p.sounds[index] = replacement.file
        p.approved = False
        p.status = "READY_FOR_APPROVAL"
        p.output_file = ""
        p.save()
        return redirect(f"/creator-ai/project/{video_id}")

    @app.route("/creator-ai/reorder-sound/<video_id>/<int:index>/<direction>", methods=["POST"])
    def creator_reorder_sound(video_id: str, index: int, direction: str):
        p = load_project(video_id)
        target = index - 1 if direction == "up" else index + 1
        if 0 <= index < len(p.sounds) and 0 <= target < len(p.sounds):
            p.sounds[index], p.sounds[target] = p.sounds[target], p.sounds[index]
            p.approved = False
            p.status = "READY_FOR_APPROVAL"
            p.save()
        return redirect(f"/creator-ai/project/{video_id}")

    @app.route("/creator-ai/clip-feedback/<video_id>/<action>", methods=["POST"])
    def creator_clip_feedback(video_id: str, action: str):
        allowed = {
            "fits", "does_not_fit", "wrong_character", "wrong_action",
            "character_not_visible", "too_much_ui", "poor_framing", "never_use",
        }
        if action not in allowed:
            return "Unknown feedback action", 400
        p = load_project(video_id)
        if not p.source_clip:
            return "Project has no selected clip", 400
        save_feedback(
            clip_path=p.source_clip,
            video_id=p.video_id,
            template_type=p.template_type,
            character_name=p.character_name,
            action=action,
            reason=str(request.form.get("reason") or "").strip(),
        )
        p.approved = False
        p.status = "READY_FOR_APPROVAL"
        p.save()
        return redirect(f"/creator-ai/project/{video_id}")

    @app.route("/creator-ai/approve/<video_id>", methods=["POST"])
    def creator_approve(video_id: str):
        p = load_project(video_id)
        answer = int(request.form.get("correct_answer") or 3)
        p.correct_answer = max(1, min(len(p.sounds) or 1, answer))
        selected_clip = str(request.form.get("source_clip") or p.source_clip).strip()
        if selected_clip in (p.source_clips or [p.source_clip]):
            p.source_clip = selected_clip
        p.approval_notes = str(request.form.get("approval_notes") or "").strip()
        p.approved = True
        p.status = "AUTO_READY" if not p.missing else "NEEDS_ASSETS"
        p.save()
        return redirect("/creator-ai")

    @app.route("/creator-ai/generate/<video_id>", methods=["POST"])
    def creator_ai_generate(video_id: str):
        try:
            render_project(video_id)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            return page("Generation error", f'<h1>Generation failed</h1><div class="card"><pre>{esc(exc)}</pre></div>', "/creator-ai"), 500
        return redirect("/creator-ai")

    @app.route("/creator-ai/draft/<name>")
    def creator_ai_draft(name: str):
        path = base / "outputs" / "drafts" / Path(name).name
        return send_file(path, conditional=True) if path.exists() else ("Draft not found", 404)

    @app.route("/creator-ai/source/<name>")
    def creator_ai_source(name: str):
        candidates = list((base / "assets" / "source" / "mined").rglob(Path(name).name))
        return send_file(candidates[0], conditional=True) if candidates else ("Source clip not found", 404)

    @app.route("/sound-library/audio/<asset_id>")
    def sound_audio(asset_id: str):
        asset = next((x for x in load_index() if x.asset_id == asset_id), None)
        if not asset:
            return "Sound not found", 404
        path = Path(asset.file)
        if not path.is_absolute():
            path = base / path
        return send_file(path, conditional=True) if path.exists() else ("Sound file missing", 404)

    @app.route("/sound-library")
    def sound_library_page():
        items = load_index()
        rows = "".join(
            f'<tr><td><audio controls preload="none" src="/sound-library/audio/{esc(x.asset_id)}"></audio></td><td>{esc(x.query)}</td><td>{esc(x.name)}</td><td>{esc(x.creator)}</td><td>{esc(x.license)}</td><td>{esc(x.risk)}</td></tr>'
            for x in items
        ) or '<tr><td colspan="6" class="muted">No downloaded sounds yet.</td></tr>'
        body = f'''
        <h1>🎵 Sound Library</h1>
        <div class="card">
          <form method="post" action="/sound-library/search">
            <input name="query" placeholder="funny scream short" required>
            <input name="count" type="number" value="4" min="1" max="12">
            <button>Find & download</button>
          </form>
        </div>
        <div class="card"><table><thead><tr><th>Preview</th><th>Query</th><th>Name</th><th>Creator</th><th>License</th><th>Risk</th></tr></thead><tbody>{rows}</tbody></table></div>
        '''
        return page("Sound Library", body, "/sound-library")

    @app.route("/sound-library/search", methods=["POST"])
    def sound_library_search():
        query = str(request.form.get("query") or "").strip()
        count = max(1, min(12, int(request.form.get("count") or 4)))
        try:
            download_freesound(query, count=count)
        except Exception as exc:
            return page("Sound search error", f'<h1>Sound search failed</h1><div class="card"><pre>{esc(exc)}</pre></div>', "/sound-library"), 500
        return redirect("/sound-library")
