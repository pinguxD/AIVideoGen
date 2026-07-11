from __future__ import annotations
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
import pandas as pd, sqlite3
from .config import CONFIG
from .db import connect, rows
from .assets import scan_assets
import csv


def render_site():
    out=Path(CONFIG.output_dir); site=out/'site'; site.mkdir(parents=True, exist_ok=True)
    con=connect(CONFIG.db_path)
    all_rows=rows(con, 'SELECT * FROM videos ORDER BY opportunity_score DESC LIMIT 1000')
    env=Environment(loader=FileSystemLoader('templates'), autoescape=select_autoescape())
    assets=scan_assets()
    sound_rows=[]
    sound_csv=out/'sound_finder.csv'
    if sound_csv.exists():
        with sound_csv.open('r', encoding='utf-8') as f:
            sound_rows=list(csv.DictReader(f))
    mined_count=len([p for p in __import__('pathlib').Path('assets/source/mined').rglob('*')]) if __import__('pathlib').Path('assets/source/mined').exists() else 0
    pages={
        'index.html': ('index.html', {'videos': all_rows[:50], 'assets':assets}),
        'library.html': ('library.html', {'videos': all_rows, 'assets':assets}),
        'auto_studio.html': ('auto_studio.html', {'videos': all_rows, 'assets':assets}),
        'assets.html': ('assets.html', {'assets':assets, 'mined_count': mined_count}),
        'sounds.html': ('sounds.html', {'sounds': sound_rows, 'assets':assets}),
        'trends.html': ('trends.html', {'videos': all_rows, 'group':'game'}),
        'series.html': ('trends.html', {'videos': all_rows, 'group':'template_type'}),
        'hooks.html': ('trends.html', {'videos': all_rows, 'group':'hook_type'}),
        'diagnostics.html': ('diagnostics.html', {'videos': all_rows, 'assets':assets}),
    }
    for fname,(tpl,ctx) in pages.items():
        (site/fname).write_text(env.get_template(tpl).render(**ctx), encoding='utf-8')
    # Daily mission markdown
    top_auto=[v for v in all_rows if v.get('auto_recreate_verdict')=='AUTO CREATE'][:5]
    top_need=[v for v in all_rows if v.get('auto_recreate_verdict')=='NEEDS ASSETS'][:10]
    md=['# Daily Mission\n']
    if top_auto:
        v=top_auto[0]; md.append(f"## Make this automatically now\n- **{v['title']}**\n- Template: {v['template_type']}\n- Opportunity: {v['opportunity_score']}\n- URL: {v['url']}\n")
    if top_need:
        md.append('\n## Needs assets\n')
        for v in top_need[:5]: md.append(f"- {v['title']} — missing: {v['missing_assets']} — {v['url']}")
    (out/'daily_mission.md').write_text('\n'.join(md), encoding='utf-8')
