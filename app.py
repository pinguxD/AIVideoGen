from __future__ import annotations

from flask import Flask, redirect, request, jsonify, render_template_string, send_file, url_for
from pathlib import Path
from urllib.parse import unquote
import html
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# Always resolve paths from the project folder, not from wherever the terminal happens to be.
BASE = Path(__file__).resolve().parent
OUTPUTS = BASE / "outputs"
REPORT = OUTPUTS / "clip_miner_report.csv"
TREND_REPORT = OUTPUTS / "trend_report.csv"
FINAL_OPPORTUNITIES = OUTPUTS / "final_opportunities.csv"
TOP_50 = OUTPUTS / "top_50.csv"
SOUND_FINDER = OUTPUTS / "sound_finder.csv"
SOUND_INTEL = OUTPUTS / "sound_intelligence.csv"

MINED = BASE / "assets" / "source" / "mined"
RAW = BASE / "assets" / "raw_gameplay"
PROCESSED = BASE / "assets" / "processed_gameplay"
SOUND_ASSETS = BASE / "assets" / "sounds"
ASSET_INDEX = BASE / "assets" / "asset_index.csv"

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}
REPORT_COLUMNS = ["source", "start", "end", "score", "reason", "output", "user_rating"]

NAV_ITEMS = [
    ("/studio", "Studio"),
    ("/clips", "🎬 Clip Review"),
    ("/recommendations", "Recommended Shorts"),
    ("/auto-studio", "Auto Studio"),
    ("/creator-ai", "🤖 Creator AI"),
    ("/sound-library", "🎵 Sound Library"),
    ("/library", "Viral Library"),
    ("/trends", "Trend Groups"),
    ("/assets", "Assets"),
    ("/sounds", "Sounds"),
    ("/learning", "🧠 AI Learning"),
    ("/my-channel", "📈 My Channel"),
    ("/diagnostics", "Diagnostics"),
    ("/reference-queue", "Reference Queue"),
    ("/analysis-review", "Analysis Review"),
    ("/recreation-lab", "Roblox Recreation Lab"),
    ("/audio-autopilot", "Audio Intelligence Autopilot"),
    ("/roblox-generation", "Roblox Studio Generation"),
    ("/roblox-plugin", "Roblox Studio Plugin Bridge"),
    ("/roblox-brain", "Roblox Brain"),
]


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def count_files(folder: Path, exts: set[str] | None = None) -> int:
    if not folder.exists():
        return 0
    files = [p for p in folder.rglob("*") if p.is_file()]
    if exts:
        files = [p for p in files if p.suffix.lower() in exts]
    return len(files)


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path).fillna("")
    except Exception:
        return pd.DataFrame()


def load_report() -> pd.DataFrame:
    df = load_csv(REPORT)
    if df.empty and not REPORT.exists():
        df = pd.DataFrame(columns=REPORT_COLUMNS)
    for col in REPORT_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df.fillna("")


def save_report(df: pd.DataFrame) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(REPORT, index=False)


def load_recommendations() -> pd.DataFrame:
    # final_opportunities is the cleaned production list; trend_report is the broader scanner output.
    df = load_csv(FINAL_OPPORTUNITIES)
    if df.empty:
        df = load_csv(TREND_REPORT)
    return df


def load_library() -> pd.DataFrame:
    df = load_csv(TOP_50)
    if df.empty:
        df = load_recommendations()
    return df


def resolve_project_path(value: str | Path) -> Path:
    text = unquote(str(value or "")).strip().strip('"').strip("'")
    text = text.replace("\\", "/")
    p = Path(text)

    if not p.is_absolute():
        p = BASE / p

    # If the CSV came from an older project path, keep only the filename as fallback below.
    return p.resolve()


def clip_path_for_row(row_index: int) -> Path | None:
    df = load_report()
    if row_index < 0 or row_index >= len(df):
        return None

    output = str(df.at[row_index, "output"] if "output" in df.columns else "")
    video_path = resolve_project_path(output)

    if video_path.exists():
        return video_path

    mined_guess = MINED / video_path.name
    if mined_guess.exists():
        return mined_guess.resolve()

    return video_path


def badge(text: str) -> str:
    value = str(text or "")
    cls = "badge muted-badge"
    if value in {"AUTO_CREATE", "RECREATE NOW", "MAKE THIS TODAY", "MAKE"}:
        cls = "badge good-badge"
    elif value in {"NEEDS_ASSETS", "NEEDS ASSETS", "REVIEW"}:
        cls = "badge warn-badge"
    elif value in {"MANUAL_ONLY", "SKIP"}:
        cls = "badge bad-badge"
    return f'<span class="{cls}">{esc(value)}</span>'


def nav_html(active: str = "") -> str:
    links = []
    for href, label in NAV_ITEMS:
        cls = "active" if href == active else ""
        links.append(f'<a class="{cls}" href="{href}">{label}</a>')
    return "".join(links)


def page(title: str, body: str, active: str = "") -> str:
    return render_template_string("""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }}</title>
<style>
:root {
    --bg:#080b12;
    --panel:#111827;
    --panel2:#151c2c;
    --line:#263247;
    --text:#f4f7fb;
    --muted:#9da8b4;
    --blue:#8bd3ff;
    --accent:#7c5cff;
    --green:#87ffae;
    --red:#ff9ca8;
    --yellow:#ffd37a;
}
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--text); font-family:Inter,Segoe UI,Arial,sans-serif; }
.wrap { display:flex; min-height:100vh; }
aside { width:250px; background:#0f1724; padding:20px; position:fixed; height:100vh; border-right:1px solid var(--line); overflow:auto; }
main { margin-left:250px; padding:26px; width:calc(100% - 250px); max-width:1650px; }
a { color:var(--blue); }
aside a { display:block; padding:11px 10px; text-decoration:none; color:#d9e6ef; border-radius:10px; margin:2px 0; }
aside a:hover, aside a.active { background:#1b2638; color:#ffffff; }
.brand { margin:0 0 18px; font-size:22px; }
.card { background:var(--panel); border:1px solid var(--line); border-radius:16px; padding:18px; margin:14px 0; box-shadow:0 8px 30px #0003; }
.card.tight { padding:14px; margin:10px 0; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(185px,1fr)); gap:12px; }
.two-col { display:grid; grid-template-columns:minmax(420px, 1.1fr) minmax(420px, .9fr); gap:16px; align-items:start; }
.three-col { display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:12px; }
.score { font-size:30px; font-weight:900; line-height:1; }
.stat-label { margin:6px 0 0; color:#cbd5e1; font-size:13px; }
.muted { color:var(--muted); }
.good { color:var(--green); }
.bad { color:var(--red); }
.warn { color:var(--yellow); }
video { width:100%; max-height:360px; border-radius:12px; background:#000; display:block; margin:10px 0 14px; }
button, .btn { padding:10px 14px; margin:4px; border:0; border-radius:9px; cursor:pointer; font-weight:800; background:#263544; color:white; text-decoration:none; display:inline-block; }
button:hover, .btn:hover { background:#3e5870; }
.rating button.active { background:#2c8f58; }
table { width:100%; border-collapse:collapse; font-size:13px; }
th,td { border-bottom:1px solid var(--line); padding:9px; text-align:left; vertical-align:top; }
th { color:#b6c6d6; }
input, select { background:#0b1118; color:white; border:1px solid #314152; border-radius:8px; padding:9px; }
.path { font-family:Consolas,monospace; font-size:12px; color:#b6c6d6; overflow-wrap:anywhere; }
.clip-card.rated-fade { opacity:.45; transition:.2s; }
.badge { border-radius:999px; padding:4px 9px; font-weight:800; font-size:12px; display:inline-block; }
.good-badge { background:#0d5130; color:#a7ffca; }
.warn-badge { background:#5a4100; color:#ffe18c; }
.bad-badge { background:#58151c; color:#ffb3bb; }
.muted-badge { background:#263544; color:#b6c6d6; }
.small { font-size:12px; }
.row-actions { display:flex; flex-wrap:wrap; gap:4px; align-items:center; }
.section-title { display:flex; justify-content:space-between; gap:12px; align-items:center; }
.thumbnail { width:96px; border-radius:8px; }
@media (max-width: 1100px) {
    aside { position:static; width:100%; height:auto; }
    main { margin-left:0; width:100%; padding:18px; }
    .wrap { display:block; }
    .two-col { grid-template-columns:1fr; }
}
</style>
</head>
<body>
<div class="wrap">
<aside>
    <h2 class="brand">⚡ Trend Radar X</h2>
    {{ nav|safe }}
    <p class="muted small">Creator AI — one dashboard layout.</p>
</aside>
<main>{{ body|safe }}</main>
</div>
</body>
</html>
""", title=title, body=body, nav=nav_html(active))


def stats_values() -> dict[str, int]:
    clips = load_report()
    recs = load_recommendations()
    library = load_library()

    total_clip_rows = len(clips)
    rated = len(clips[clips["user_rating"].astype(str) != ""]) if total_clip_rows else 0
    unrated = total_clip_rows - rated
    ratings_num = pd.to_numeric(clips["user_rating"], errors="coerce") if total_clip_rows else pd.Series(dtype=float)
    five_star = int((ratings_num == 5).sum()) if total_clip_rows else 0

    auto_ready = 0
    if not recs.empty:
        if "auto_status" in recs.columns:
            auto_ready = len(recs[recs["auto_status"].astype(str) == "AUTO_CREATE"])
        elif "recreate_verdict" in recs.columns:
            auto_ready = len(recs[recs["recreate_verdict"].astype(str).str.contains("RECREATE|MAKE", case=False, na=False)])

    return {
        "top_videos": len(library),
        "recommended": len(recs),
        "mined_clips": count_files(MINED, VIDEO_EXT),
        "clip_rows": total_clip_rows,
        "rated": rated,
        "unrated": unrated,
        "five_star": five_star,
        "raw_gameplay": count_files(RAW, VIDEO_EXT),
        "processed_gameplay": count_files(PROCESSED, VIDEO_EXT),
        "sound_assets": count_files(SOUND_ASSETS, AUDIO_EXT),
        "auto_ready": auto_ready,
    }


def stat_card(value: int | str, label: str) -> str:
    return f'<div class="card tight"><div class="score">{esc(value)}</div><p class="stat-label">{esc(label)}</p></div>'


def render_stats(mode: str = "studio") -> str:
    s = stats_values()
    if mode == "clips":
        cards = [
            (s["mined_clips"], "Mined clips"),
            (s["clip_rows"], "Rows in clip report"),
            (s["unrated"], "Unrated clips"),
            (s["five_star"], "5-star clips"),
        ]
    elif mode == "assets":
        cards = [
            (s["mined_clips"], "Mined video clips"),
            (s["raw_gameplay"], "Raw gameplay files"),
            (s["processed_gameplay"], "Processed gameplay files"),
            (s["sound_assets"], "Sound assets"),
        ]
    else:
        cards = [
            (s["top_videos"], "Top videos shown"),
            (s["recommended"], "Recommended shorts"),
            (s["mined_clips"], "Mined clips"),
            (s["unrated"], "Unrated clips"),
            (s["five_star"], "5-star clips"),
            (s["sound_assets"], "Sound assets"),
            (s["auto_ready"], "Auto-create ready"),
        ]
    return '<div class="grid">' + ''.join(stat_card(v, l) for v, l in cards) + '</div>'


def render_table(df: pd.DataFrame, columns: list[str], limit: int = 50) -> str:
    if df.empty:
        return '<p class="muted">No data yet.</p>'
    available = [c for c in columns if c in df.columns]
    if not available:
        available = list(df.columns[:8])
    headers = ''.join(f'<th>{esc(c)}</th>' for c in available)
    rows = ''
    for _, r in df.head(limit).iterrows():
        rows += '<tr>'
        for c in available:
            value = r.get(c, '')
            if c in {"url", "pixabay", "freesound", "myinstants"} and str(value):
                value = f'<a href="{esc(value)}" target="_blank">open</a>'
            elif c in {"thumbnail"} and str(value):
                value = f'<img class="thumbnail" src="{esc(value)}">'
            elif c in {"auto_status", "production_verdict", "recreate_verdict", "ai_verdict", "auto_recreate_verdict"}:
                value = badge(str(value))
            else:
                value = esc(value)
            rows += f'<td>{value}</td>'
        rows += '</tr>'
    return f'<table><tr>{headers}</tr>{rows}</table>'


def render_recommended_shorts(limit: int = 12) -> str:
    df = load_recommendations()
    if df.empty:
        return '<div class="card"><h2>Recommended Shorts</h2><p class="muted">No recommendation file found yet.</p></div>'
    if "opportunity_score" in df.columns:
        df = df.assign(_sort_score=pd.to_numeric(df["opportunity_score"], errors="coerce").fillna(0)).sort_values("_sort_score", ascending=False)
    cols = ["opportunity_score", "title", "auto_status", "production_verdict", "auto_recreate_verdict", "game", "template_type", "missing_assets", "url"]
    return f'''
    <div class="card">
        <div class="section-title"><h2>Recommended Shorts</h2><a href="/recommendations">View all</a></div>
        {render_table(df, cols, limit)}
    </div>
    '''


def render_clip_cards(limit: int = 8, filter_type: str = "unrated", link_base: str = "/studio") -> str:
    df = load_report()
    if filter_type == "unrated":
        shown = df[df["user_rating"].astype(str) == ""]
    elif filter_type == "rated":
        shown = df[df["user_rating"].astype(str) != ""]
    elif filter_type == "five":
        shown = df[df["user_rating"].astype(str) == "5"]
    else:
        shown = df

    param = "filter" if link_base == "/clips" else "clip_filter"
    body = f'''
    <div class="card">
        <div class="section-title">
            <h2>Clip Review</h2>
            <div>
                <a href="{link_base}?{param}=unrated">Unrated</a> |
                <a href="{link_base}?{param}=all">All</a> |
                <a href="{link_base}?{param}=rated">Rated</a> |
                <a href="{link_base}?{param}=five">5-star</a>
            </div>
        </div>
        <p class="muted">Click 1–5. It saves instantly to outputs/clip_miner_report.csv.</p>
    </div>
    '''

    if len(shown) == 0:
        return body + '<div class="card"><p class="muted">No clips found for this filter.</p></div>'

    for real_index, r in shown.head(limit).iterrows():
        video_path = clip_path_for_row(int(real_index))
        exists = bool(video_path and video_path.exists())
        rating = str(r.get("user_rating", ""))
        missing = "" if exists else f'<p class="bad"><b>Video file not found:</b></p><p class="path">{esc(video_path)}</p>'
        buttons = ""
        for n in [1, 2, 3, 4, 5]:
            active = " active" if rating == str(n) else ""
            buttons += f'<button class="rate-btn-{real_index}{active}" onclick="rateClip({int(real_index)}, {n})">{n}</button>'
        body += f'''
        <div class="card clip-card" id="clip-{int(real_index)}">
            <h3>Clip row {int(real_index)}</h3>
            <video controls preload="metadata" src="/clip_video/{int(real_index)}"></video>
            {missing}
            <p><b>Source:</b> <span class="path">{esc(r.get("source", ""))}</span></p>
            <p><b>Output:</b> <span class="path">{esc(r.get("output", ""))}</span></p>
            <p><b>AI Score:</b> {esc(r.get("score", ""))} &nbsp; <b>Reason:</b> {esc(r.get("reason", ""))}</p>
            <p><b>Current rating:</b> <span id="rating-{int(real_index)}">{esc(rating)}</span></p>
            <div class="rating row-actions">{buttons}<span class="good" id="saved-{int(real_index)}"></span></div>
        </div>
        '''

    body += """
<script>
async function rateClip(rowIndex, rating) {
    const response = await fetch('/rate_clip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ row_index: rowIndex, rating: rating })
    });
    const data = await response.json();
    if (data.ok) {
        document.getElementById('rating-' + rowIndex).innerText = rating;
        document.getElementById('saved-' + rowIndex).innerText = ' Saved';
        document.querySelectorAll('.rate-btn-' + rowIndex).forEach(btn => btn.classList.remove('active'));
        const buttons = document.querySelectorAll('.rate-btn-' + rowIndex);
        if (buttons[rating - 1]) buttons[rating - 1].classList.add('active');
        setTimeout(() => {
            document.getElementById('saved-' + rowIndex).innerText = '';
            const params = new URLSearchParams(window.location.search);
            const f = params.get('filter') || params.get('clip_filter') || 'unrated';
            if (f === 'unrated') {
                const card = document.getElementById('clip-' + rowIndex);
                if (card) card.classList.add('rated-fade');
            }
        }, 500);
    } else {
        alert(data.error || 'Save failed');
    }
}
</script>
"""
    return body


@app.route("/")
def root():
    return redirect("/studio")


@app.route("/studio")
def studio():
    clip_filter = request.args.get("clip_filter", "unrated")
    body = f'''
    <h1>Studio</h1>
    {render_stats("studio")}
    <div class="two-col">
        <div>{render_recommended_shorts(limit=12)}</div>
        <div>{render_clip_cards(limit=8, filter_type=clip_filter, link_base="/studio")}</div>
    </div>
    '''
    return page("Studio", body, "/studio")


@app.route("/clips")
def clips():
    filter_type = request.args.get("filter", "unrated")
    body = f'<h1>🎬 Clip Review</h1>{render_stats("clips")}{render_clip_cards(limit=999999, filter_type=filter_type, link_base="/clips")}'
    return page("Clip Review", body, "/clips")


@app.route("/recommendations")
def recommendations():
    df = load_recommendations()
    if "opportunity_score" in df.columns:
        df = df.assign(_sort_score=pd.to_numeric(df["opportunity_score"], errors="coerce").fillna(0)).sort_values("_sort_score", ascending=False)
    cols = ["opportunity_score", "title", "auto_status", "production_verdict", "auto_recreate_score", "auto_recreate_verdict", "view_count", "subscriber_count", "views_per_day", "game", "template_type", "missing_assets", "url"]
    body = f'<h1>Recommended Shorts</h1>{render_stats("studio")}<div class="card">{render_table(df, cols, 500)}</div>'
    return page("Recommended Shorts", body, "/recommendations")


@app.route("/auto-studio")
def auto_studio():
    df = load_recommendations()
    if not df.empty and "auto_status" in df.columns:
        auto = df[df["auto_status"].astype(str) == "AUTO_CREATE"]
        needs = df[df["auto_status"].astype(str) == "NEEDS_ASSETS"]
    else:
        auto = pd.DataFrame()
        needs = df
    cols = ["opportunity_score", "title", "auto_status", "production_verdict", "required_inputs", "missing_assets", "url"]
    body = f'<h1>Auto Studio</h1>{render_stats("studio")}<div class="card"><h2>Can generate now</h2>{render_table(auto, cols, 100)}</div><div class="card"><h2>Needs assets</h2>{render_table(needs, cols, 200)}</div>'
    return page("Auto Studio", body, "/auto-studio")


@app.route("/library")
def library():
    df = load_library()
    cols = ["opportunity_score", "clone_score", "title", "ai_verdict", "recreate_verdict", "views", "subs", "views_per_day", "game_topic", "format_type", "url"]
    if "views" not in df.columns:
        cols = ["opportunity_score", "title", "production_verdict", "view_count", "subscriber_count", "views_per_day", "game", "template_type", "url"]
    body = f'<h1>Viral Library</h1>{render_stats("studio")}<div class="card">{render_table(df, cols, 500)}</div>'
    return page("Viral Library", body, "/library")


@app.route("/trends")
def trends():
    df = load_recommendations()
    if df.empty:
        grouped = pd.DataFrame()
    else:
        game_col = "game" if "game" in df.columns else "game_topic" if "game_topic" in df.columns else None
        template_col = "template_type" if "template_type" in df.columns else "format_type" if "format_type" in df.columns else None
        if game_col and template_col:
            score_col = "opportunity_score" if "opportunity_score" in df.columns else None
            view_col = "view_count" if "view_count" in df.columns else "views" if "views" in df.columns else None
            temp = df.copy()
            if score_col:
                temp[score_col] = pd.to_numeric(temp[score_col], errors="coerce").fillna(0)
            if view_col:
                temp[view_col] = pd.to_numeric(temp[view_col], errors="coerce").fillna(0)
            grouped = temp.groupby([game_col, template_col]).agg(
                videos=(template_col, "count"),
                avg_opportunity=(score_col, "mean") if score_col else (template_col, "count"),
                total_views=(view_col, "sum") if view_col else (template_col, "count"),
            ).reset_index().sort_values("avg_opportunity", ascending=False)
        else:
            grouped = df
    body = f'<h1>Trend Groups</h1>{render_stats("studio")}<div class="card">{render_table(grouped, list(grouped.columns), 300)}</div>'
    return page("Trend Groups", body, "/trends")


@app.route("/assets")
def assets():
    asset_index = load_csv(ASSET_INDEX)
    mined_files = pd.DataFrame([{"file": str(p.relative_to(BASE)), "type": "mined_clip", "size_mb": round(p.stat().st_size / 1024 / 1024, 2)} for p in sorted(MINED.rglob("*")) if p.is_file() and p.suffix.lower() in VIDEO_EXT])
    body = f'<h1>Assets</h1>{render_stats("assets")}<div class="card"><h2>Mined clips</h2>{render_table(mined_files, ["file", "type", "size_mb"], 200)}</div><div class="card"><h2>Asset index</h2>{render_table(asset_index, list(asset_index.columns), 200)}</div>'
    return page("Assets", body, "/assets")


@app.route("/sounds")
def sounds():
    finder = load_csv(SOUND_FINDER)
    intel = load_csv(SOUND_INTEL)
    body = f'<h1>Sounds</h1>{render_stats("assets")}<div class="card"><h2>Sound Finder</h2>{render_table(finder, list(finder.columns), 100)}</div><div class="card"><h2>Sound Intelligence</h2>{render_table(intel, list(intel.columns), 100)}</div>'
    return page("Sounds", body, "/sounds")


@app.route("/learning")
def learning():
    df = load_report()
    rated = df[df["user_rating"].astype(str) != ""].copy()
    if len(df) == 0:
        return page("AI Learning", '<h1>🧠 AI Learning</h1><div class="card"><p>No clip data yet.</p></div>', "/learning")
    if len(rated) == 0:
        return page("AI Learning", f'<h1>🧠 AI Learning</h1>{render_stats("clips")}<div class="card"><p>No rated clips yet. Rate clips first.</p></div>', "/learning")
    rated["user_rating"] = pd.to_numeric(rated["user_rating"], errors="coerce").fillna(0).astype(int)
    rated["score"] = pd.to_numeric(rated["score"], errors="coerce").fillna(0)
    avg_score = round(rated["score"].mean(), 2)
    avg_rating = round(rated["user_rating"].mean(), 2)
    best = rated.sort_values(["user_rating", "score"], ascending=False).head(20)
    rows = render_table(best, ["user_rating", "score", "reason", "output"], 20)
    body = f'''
    <h1>🧠 AI Learning</h1>
    {render_stats("clips")}
    <div class="grid">
        {stat_card(len(rated), "Rated clips")}
        {stat_card(avg_rating, "Average user rating")}
        {stat_card(avg_score, "Average AI score")}
    </div>
    <div class="card"><h2>Best rated clips</h2>{rows}</div>
    '''
    return page("AI Learning", body, "/learning")


@app.route("/diagnostics")
def diagnostics():
    df = load_report()
    missing = []
    for idx in range(len(df)):
        p = clip_path_for_row(idx)
        if not p or not p.exists():
            missing.append((idx, p))
    missing_rows = ''.join(f"<li>Row {idx}: <span class='path'>{esc(p)}</span></li>" for idx, p in missing[:30]) or "<li class='good'>No missing clip files found.</li>"
    body = f'''
    <h1>Diagnostics</h1>
    {render_stats("studio")}
    <div class="card">
        <p><b>Project folder:</b> <span class="path">{esc(BASE)}</span></p>
        <p><b>Clip report exists:</b> {REPORT.exists()} — <span class="path">{esc(REPORT)}</span></p>
        <p><b>Recommendations file exists:</b> {FINAL_OPPORTUNITIES.exists()} — <span class="path">{esc(FINAL_OPPORTUNITIES)}</span></p>
        <p><b>Trend report exists:</b> {TREND_REPORT.exists()} — <span class="path">{esc(TREND_REPORT)}</span></p>
        <p><b>Top 50 exists:</b> {TOP_50.exists()} — <span class="path">{esc(TOP_50)}</span></p>
        <p><b>Mined folder:</b> <span class="path">{esc(MINED)}</span></p>
        <p><b>Raw folder:</b> <span class="path">{esc(RAW)}</span></p>
        <p><b>Processed folder:</b> <span class="path">{esc(PROCESSED)}</span></p>
        <p><b>Sound folder:</b> <span class="path">{esc(SOUND_ASSETS)}</span></p>
        <p><b>Missing clips:</b> {len(missing)}</p>
    </div>
    <div class="card"><h2>Missing clip files</h2><ul>{missing_rows}</ul></div>
    '''
    return page("Diagnostics", body, "/diagnostics")


@app.route("/clip_video/<int:row_index>")
def clip_video_by_row(row_index: int):
    video_path = clip_path_for_row(row_index)
    if not video_path or not video_path.exists():
        return f"Video not found for row {row_index}: {video_path}", 404
    return send_file(video_path, mimetype="video/mp4", conditional=True)


@app.route("/rate_clip", methods=["POST"])
def rate_clip():
    data = request.get_json(silent=True) or {}
    try:
        row_index = int(data.get("row_index"))
    except Exception:
        return jsonify({"ok": False, "error": "Invalid row"})
    rating = str(data.get("rating"))
    if rating not in ["1", "2", "3", "4", "5"]:
        return jsonify({"ok": False, "error": "Invalid rating"})
    df = load_report()
    if row_index < 0 or row_index >= len(df):
        return jsonify({"ok": False, "error": "Invalid row"})
    df.at[row_index, "user_rating"] = rating
    save_report(df)
    return jsonify({"ok": True})


@app.route("/site/<path:path>")
def old_site_redirect(path: str):
    name = Path(path).stem.lower()
    mapping = {
        "index": "/studio",
        "auto_studio": "/auto-studio",
        "assets": "/assets",
        "sounds": "/sounds",
        "library": "/library",
        "trends": "/trends",
        "series": "/trends",
        "hooks": "/recommendations",
        "diagnostics": "/diagnostics",
    }
    return redirect(mapping.get(name, "/studio"))

from radar.reference_web import register_reference_routes

register_reference_routes(
    app,
    BASE,
    page,
    esc,
)

# Creator AI routes
from radar.channel_web import register_channel_routes
register_channel_routes(app, page, esc)

from radar.creator_web import register_creator_routes
register_creator_routes(app, BASE, page, render_stats, load_recommendations, esc)

from radar.analysis_review_web import register_analysis_review_routes

register_analysis_review_routes(
    app,
    page,
    esc,
)
from radar.recreation_web import register_recreation_routes

register_recreation_routes(
    app,
    page,
    esc,
)

from radar.audio_autopilot_web import register_audio_autopilot_routes

register_audio_autopilot_routes(
    app,
    page,
    esc,
)
from radar.roblox_generation_web import register_roblox_generation_routes

register_roblox_generation_routes(
    app,
    page,
    esc,
)
from radar.roblox_plugin_web import register_roblox_plugin_routes

register_roblox_plugin_routes(
    app,
    page,
    esc,
)
from radar.roblox_brain_web import register_roblox_brain_routes

register_roblox_brain_routes(
    app,
    page,
    esc,
)
if __name__ == "__main__":
    from radar.channel_feedback import start_background_sync
    start_background_sync()
    print("Open http://127.0.0.1:5000/studio")
    app.run(debug=False)
