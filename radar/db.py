from __future__ import annotations
import sqlite3, os, json
from pathlib import Path
from datetime import datetime

SCHEMA = '''
CREATE TABLE IF NOT EXISTS videos (
    video_id TEXT PRIMARY KEY,
    title TEXT, url TEXT, channel_id TEXT, channel_title TEXT,
    subscriber_count INTEGER DEFAULT 0, view_count INTEGER DEFAULT 0,
    published_at TEXT, age_days REAL DEFAULT 0, duration_seconds INTEGER DEFAULT 0,
    game TEXT, hook_type TEXT, template_type TEXT, viral_dna TEXT,
    production_score INTEGER DEFAULT 0, production_verdict TEXT, required_tools TEXT, missing_skills TEXT, why_make TEXT,
    auto_recreate_score INTEGER DEFAULT 0, auto_recreate_verdict TEXT, required_inputs TEXT, missing_assets TEXT,
    opportunity_score INTEGER DEFAULT 0, title_variants TEXT,
    first_seen TEXT, last_seen TEXT, raw_json TEXT
);
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT, scanned_at TEXT, view_count INTEGER, subscriber_count INTEGER, opportunity_score INTEGER
);
CREATE TABLE IF NOT EXISTS sounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sound_name TEXT, trend_score INTEGER, copyright_risk TEXT, search_url TEXT, notes TEXT, first_seen TEXT
);
'''

def connect(path='outputs/trend_radar_x.db'):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con=sqlite3.connect(path, timeout=30, check_same_thread=False)
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('PRAGMA busy_timeout=30000')
    con.executescript(SCHEMA)
    con.commit()
    return con

def upsert_video(con, v: dict):
    now=datetime.utcnow().isoformat(timespec='seconds')
    existing=con.execute('SELECT first_seen FROM videos WHERE video_id=?',(v['video_id'],)).fetchone()
    first=existing[0] if existing else now
    fields=['video_id','title','url','channel_id','channel_title','subscriber_count','view_count','published_at','age_days','duration_seconds','game','hook_type','template_type','viral_dna','production_score','production_verdict','required_tools','missing_skills','why_make','auto_recreate_score','auto_recreate_verdict','required_inputs','missing_assets','opportunity_score','title_variants']
    data={k:v.get(k) for k in fields}
    data['first_seen']=first; data['last_seen']=now; data['raw_json']=json.dumps(v, ensure_ascii=False)
    cols=list(data.keys())
    placeholders=','.join(['?']*len(cols))
    updates=','.join([f'{c}=excluded.{c}' for c in cols if c!='video_id'])
    con.execute(f"INSERT INTO videos ({','.join(cols)}) VALUES ({placeholders}) ON CONFLICT(video_id) DO UPDATE SET {updates}", [data[c] for c in cols])
    con.execute('INSERT INTO snapshots(video_id, scanned_at, view_count, subscriber_count, opportunity_score) VALUES (?,?,?,?,?)', (v['video_id'], now, v.get('view_count',0), v.get('subscriber_count',0), v.get('opportunity_score',0)))
    con.commit()

def rows(con, query='SELECT * FROM videos ORDER BY opportunity_score DESC LIMIT 500'):
    con.row_factory=sqlite3.Row
    return [dict(r) for r in con.execute(query).fetchall()]
