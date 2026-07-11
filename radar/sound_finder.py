from __future__ import annotations
from pathlib import Path
from urllib.parse import quote_plus
import csv, re, requests

SOUNDS = Path('assets/sounds')
REPORT = Path('outputs/sound_finder.csv')

SOUND_PROFILES = {
    'guess_voice': ['funny scream','aaaaah scream','auughh scream','vine boom','metal pipe'],
    'sound_replacement': ['monster scream','funny scream','eagle scream','vine boom','metal pipe'],
    'meme_caption': ['vine boom','metal pipe','cartoon boing','funny scream'],
    'fact_card': ['whoosh','pop sound','ding sound','click sound'],
    'choice_game': ['correct ding','wrong buzzer','vine boom','suspense hit'],
}

SAFE_SITES = [
    ('Pixabay', 'https://pixabay.com/sound-effects/search/{q}/', 'Often free-to-use, check license on asset page.'),
    ('Freesound', 'https://freesound.org/search/?q={q}', 'Check each clip license; prefer CC0.'),
    ('MyInstants', 'https://www.myinstants.com/en/search/?name={q}', 'Meme soundboard; copyright risk varies, manual check.'),
]


def needed_sound_keywords(template_type: str) -> list[str]:
    return SOUND_PROFILES.get(template_type, ['funny scream','vine boom','metal pipe'])


def local_sound_count() -> int:
    SOUNDS.mkdir(parents=True, exist_ok=True)
    return len([p for p in SOUNDS.rglob('*') if p.suffix.lower() in {'.mp3','.wav','.ogg','.m4a'}])


def build_sound_searches(videos: list[dict]) -> list[dict]:
    SOUNDS.mkdir(parents=True, exist_ok=True); REPORT.parent.mkdir(exist_ok=True)
    wanted=[]
    for v in videos:
        tmpl=v.get('template_type','')
        for kw in needed_sound_keywords(tmpl):
            wanted.append((kw, tmpl, v.get('title','')))
    # aggregate frequency
    counts={}
    examples={}
    for kw,tmpl,title in wanted:
        counts[kw]=counts.get(kw,0)+1
        examples.setdefault(kw, title)
    rows=[]
    for kw,count in sorted(counts.items(), key=lambda x:x[1], reverse=True):
        q=quote_plus(kw)
        risk='Low/Medium' if kw in ['whoosh','pop sound','ding sound','click sound','cartoon boing','correct ding','wrong buzzer'] else 'Medium/High - manual rights check'
        rows.append({
            'sound':kw,
            'needed_by_projects':count,
            'copyright_risk':risk,
            'example_video':examples.get(kw,''),
            'pixabay':SAFE_SITES[0][1].format(q=q),
            'freesound':SAFE_SITES[1][1].format(q=q),
            'myinstants':SAFE_SITES[2][1].format(q=q),
            'notes':'Download only reusable/allowed sounds. Prefer CC0/public domain or sounds you create yourself.'
        })
    with REPORT.open('w', newline='', encoding='utf-8') as f:
        if rows:
            w=csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    return rows


def download_url(url: str, filename: str|None=None) -> Path:
    """Manual helper: paste a direct .mp3/.wav/.ogg URL you are allowed to use.
    This avoids scraping random soundboards blindly.
    """
    SOUNDS.mkdir(parents=True, exist_ok=True)
    if filename is None:
        filename = re.sub(r'[^a-zA-Z0-9_.-]+','_', url.split('/')[-1] or 'sound.mp3')
    out=SOUNDS/filename
    r=requests.get(url, timeout=30)
    r.raise_for_status()
    out.write_bytes(r.content)
    return out
