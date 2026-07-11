from __future__ import annotations
from pathlib import Path
import csv, json

ASSETS = Path('assets')
SOURCE = ASSETS/'source'
SOUNDS = ASSETS/'sounds'
RAW = ASSETS/'raw_gameplay'
META = ASSETS/'asset_index.csv'

VIDEO_EXT={'.mp4','.mov','.mkv','.webm'}
IMAGE_EXT={'.png','.jpg','.jpeg','.webp'}
SOUND_EXT={'.mp3','.wav','.ogg','.m4a'}


def ensure_dirs():
    SOURCE.mkdir(parents=True, exist_ok=True); SOUNDS.mkdir(parents=True, exist_ok=True); RAW.mkdir(parents=True, exist_ok=True)


def scan_assets() -> dict:
    ensure_dirs()
    src = [p for p in SOURCE.rglob('*') if p.suffix.lower() in VIDEO_EXT|IMAGE_EXT]
    snd = [p for p in SOUNDS.rglob('*') if p.suffix.lower() in SOUND_EXT]
    raw = [p for p in RAW.rglob('*') if p.suffix.lower() in VIDEO_EXT]
    write_index(src, snd)
    return {'source': len(src), 'sounds': len(snd), 'raw_gameplay': len(raw), 'source_files': [str(p) for p in src], 'sound_files':[str(p) for p in snd], 'raw_files':[str(p) for p in raw]}


def write_index(src, snd):
    with META.open('w', newline='', encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['path','type','stem','tags'])
        for p in src: w.writerow([str(p),'source',p.stem,guess_tags(p.stem)])
        for p in snd: w.writerow([str(p),'sound',p.stem,guess_tags(p.stem)])


def guess_tags(name: str) -> str:
    n=name.lower(); tags=[]
    for t in ['monster','duckman','intern','doctor','scream','voice','funny','roblox','animal','hospital','grow','garden','background','walking','closeup','clip','mined','raw']:
        if t in n: tags.append(t)
    return ','.join(tags)
