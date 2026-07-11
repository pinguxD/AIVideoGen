from __future__ import annotations
from pathlib import Path
from urllib.parse import quote_plus
import csv

SOUND_KEYWORDS=['scream','ahhh','vine boom','metal pipe','eagle scream','goofy scream','auughh','roblox oof','funny scream']

def build_sound_report(videos):
    out=Path('outputs'); out.mkdir(exist_ok=True)
    rows=[]
    for kw in SOUND_KEYWORDS:
        score=50
        for v in videos:
            blob=(v.get('title','')+' '+v.get('viral_dna','')).lower()
            if kw in blob: score+=5
        risk='Low/Medium' if kw not in ['roblox oof','goofy scream'] else 'High - manual rights check'
        rows.append({'sound':kw,'trend_score':min(100,score),'copyright_risk':risk,'search_links':f'https://www.myinstants.com/en/search/?name={quote_plus(kw)} | https://pixabay.com/sound-effects/search/{quote_plus(kw)}/'})
    with open(out/'sound_intelligence.csv','w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
    return rows
