from __future__ import annotations
from pathlib import Path
import html, json, pandas as pd

def esc(x): return html.escape(str(x if x is not None else ''))

def badge(status):
    cls={'AUTO_CREATE':'good','NEEDS_ASSETS':'warn','MANUAL_ONLY':'bad'}.get(status,'muted')
    return f'<span class="badge {cls}">{esc(status)}</span>'

def layout(title, body):
    nav=''.join([f'<a href="{p}.html">{n}</a>' for p,n in [('index','Today'),('library','Library'),('auto_studio','Auto Studio'),('trends','Trends'),('diagnostics','Diagnostics')]])
    return f'''<!doctype html><html><head><meta charset="utf-8"><title>{esc(title)}</title><style>
    body{{margin:0;background:#0b0d10;color:#f4f4f4;font-family:Inter,Segoe UI,Arial,sans-serif}} a{{color:#8bd3ff}} .wrap{{display:flex;min-height:100vh}} aside{{width:220px;background:#111820;padding:20px;position:fixed;height:100vh}} main{{margin-left:260px;padding:28px;max-width:1300px}} aside a{{display:block;padding:10px 8px;text-decoration:none;color:#d9e6ef;border-radius:8px}} aside a:hover{{background:#1e2a35}} .card{{background:#151a21;border:1px solid #25313d;border-radius:14px;padding:18px;margin:14px 0;box-shadow:0 8px 30px #0003}} table{{width:100%;border-collapse:collapse;font-size:13px}} th,td{{border-bottom:1px solid #27323f;padding:9px;text-align:left;vertical-align:top}} th{{color:#b6c6d6}} .badge{{border-radius:999px;padding:4px 9px;font-weight:700;font-size:12px}} .good{{background:#0d5130;color:#a7ffca}} .warn{{background:#5a4100;color:#ffe18c}} .bad{{background:#58151c;color:#ffb3bb}} .muted{{color:#9da8b4}} .score{{font-size:24px;font-weight:800}} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}} code{{background:#0a0f14;padding:2px 5px;border-radius:5px}}
    </style></head><body><div class="wrap"><aside><h2>Trend Radar X</h2>{nav}<p class="muted">Creator AI version</p></aside><main>{body}</main></div></body></html>'''

def table(rows, limit=100):
    if not rows: return '<p class="muted">No data yet.</p>'
    cols=['opportunity_score','title','auto_status','production_verdict','auto_recreate_score','production_score','view_count','subscriber_count','views_per_day','game','template_type','missing_assets','url']
    out='<table><tr>'+''.join(f'<th>{c}</th>' for c in cols)+'</tr>'
    for r in rows[:limit]:
        out+='<tr>'
        for c in cols:
            v=r.get(c,'')
            if c=='url' and v: v=f'<a href="{esc(v)}" target="_blank">open</a>'
            elif c=='auto_status': v=badge(v)
            elif isinstance(v,(list,dict)): v=esc(json.dumps(v))
            else: v=esc(v)
            out+=f'<td>{v}</td>'
        out+='</tr>'
    return out+'</table>'

def render_site(videos, out_dir='outputs/site'):
    site=Path(out_dir); site.mkdir(parents=True, exist_ok=True)
    videos=sorted(videos, key=lambda x:x.get('opportunity_score',0), reverse=True)
    auto=[v for v in videos if v.get('auto_status')=='AUTO_CREATE']
    needs=[v for v in videos if v.get('auto_status')=='NEEDS_ASSETS']
    manual=[v for v in videos if v.get('auto_status')=='MANUAL_ONLY']
    cards=f'''<h1>Today’s Mission</h1><div class="grid">
    <div class="card"><div class="score">{len(videos)}</div><p>Usable candidates</p></div>
    <div class="card"><div class="score">{len(auto)}</div><p>Auto-create now</p></div>
    <div class="card"><div class="score">{len(needs)}</div><p>Need assets</p></div>
    <div class="card"><div class="score">{len(manual)}</div><p>Manual only</p></div></div>'''
    best = videos[0] if videos else None
    mission=''
    if best:
        mission=f'''<div class="card"><h2>Best opportunity</h2><h3>{esc(best.get('title'))}</h3><p>{badge(best.get('auto_status'))} Opportunity <b>{best.get('opportunity_score')}</b> | Auto <b>{best.get('auto_recreate_score')}</b> | Production <b>{best.get('production_score')}</b></p><p><b>Missing:</b> {esc(best.get('missing_assets'))}</p><p><b>Why:</b> {esc(best.get('why_make'))}</p><p><a href="{esc(best.get('url'))}" target="_blank">Open viral example</a></p></div>'''
    (site/'index.html').write_text(layout('Today', cards+mission+'<div class="card"><h2>Top opportunities</h2>'+table(videos,50)+'</div>'), encoding='utf-8')
    (site/'library.html').write_text(layout('Library','<h1>Viral Library</h1><div class="card">'+table(videos,500)+'</div>'), encoding='utf-8')
    (site/'auto_studio.html').write_text(layout('Auto Studio',f'<h1>Auto Studio</h1><div class="card"><h2>Can generate now</h2>{table(auto,100)}</div><div class="card"><h2>Needs assets</h2>{table(needs,100)}</div>'), encoding='utf-8')
    # Trends grouped by template/game
    grp={}
    for v in videos:
        key=f"{v.get('game','Unknown')} / {v.get('template_type','Unknown')}"
        grp.setdefault(key,[]).append(v)
    trend_rows=[]
    for k,items in grp.items():
        trend_rows.append({'title':k,'opportunity_score':round(sum(i.get('opportunity_score',0) for i in items)/len(items),1),'view_count':sum(i.get('view_count',0) for i in items),'subscriber_count':'','views_per_day':round(sum(i.get('views_per_day',0) for i in items),1),'auto_status':f'{sum(1 for i in items if i.get("auto_status")=="AUTO_CREATE")} auto','production_verdict':f'{len(items)} videos','auto_recreate_score':'','production_score':'','game':'','template_type':'','missing_assets':'','url':''})
    trend_rows=sorted(trend_rows,key=lambda x:x['opportunity_score'],reverse=True)
    (site/'trends.html').write_text(layout('Trends','<h1>Trend Groups</h1><div class="card">'+table(trend_rows,200)+'</div>'), encoding='utf-8')
    diag=f'<h1>Diagnostics</h1><div class="card"><p>All candidates are stored in <code>outputs/trend_report.csv</code>.</p><p>Use this page to verify if the scanner is over-filtering.</p></div><div class="card"><h2>Status split</h2><ul><li>Auto-create: {len(auto)}</li><li>Needs assets: {len(needs)}</li><li>Manual only: {len(manual)}</li></ul></div>'
    (site/'diagnostics.html').write_text(layout('Diagnostics',diag), encoding='utf-8')
