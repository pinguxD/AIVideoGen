from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from rich.console import Console
from .config import CONFIG
from .youtube import YouTubeClient, parse_duration_seconds
from .assets import scan_assets
from .gameplay_miner import mine_raw_gameplay
from .sound_finder import build_sound_searches
from .scoring import classify_hook, detect_game, template_type, production_score, auto_recreate, opportunity_score, viral_dna, title_variants
from .db import connect, upsert_video

console=Console()

def run_scan():
    out=Path(CONFIG.output_dir); (out/'diagnostics').mkdir(parents=True, exist_ok=True)
    
    if CONFIG.mine_raw_gameplay:
        try:
            hits = mine_raw_gameplay(max_clips_per_file=CONFIG.max_mined_clips_per_file, clip_len=CONFIG.mined_clip_length_seconds)
            console.print(f'[cyan]Raw gameplay miner:[/] {len(hits)} clips registered/mined')
        except Exception as e:
            console.print(f'[yellow]Raw gameplay miner skipped/failed: {e}[/]')
    asset_index=scan_assets()
    console.print(f'[cyan]Asset library:[/] {asset_index["source"]} source files, {asset_index["sounds"]} sounds, {asset_index.get("raw_gameplay",0)} raw gameplay files')
    yt=YouTubeClient(CONFIG.youtube_api_key)
    raw=[]; seen=set()
    for q in CONFIG.queries:
        try:
            items=yt.search(q, CONFIG.days_back, CONFIG.max_results_per_query, CONFIG.region_code)
        except Exception as e:
            console.print(f'[red]Search failed for {q}: {e}[/]')
            continue
        for it in items:
            vid=it.get('id',{}).get('videoId')
            if vid and vid not in seen:
                seen.add(vid); raw.append({'video_id':vid,'query':q,'search_title':it.get('snippet',{}).get('title','')})
            if len(raw)>=CONFIG.max_total_candidates: break
        if len(raw)>=CONFIG.max_total_candidates: break
    pd.DataFrame(raw).to_csv(out/'diagnostics'/'raw_candidates.csv', index=False)
    console.print(f'[green]Raw candidates:[/] {len(raw)}')
    vids=yt.videos([r['video_id'] for r in raw])
    channels=yt.channels([v['snippet']['channelId'] for v in vids])
    processed=[]; rejected=[]
    now=datetime.now(timezone.utc)
    con = connect(CONFIG.db_path)
    for v in vids:
        sn=v.get('snippet',{}); st=v.get('statistics',{}); cd=v.get('contentDetails',{})
        cid=sn.get('channelId',''); ch=channels.get(cid,{})
        views=int(st.get('viewCount',0) or 0); subs=int(ch.get('statistics',{}).get('subscriberCount',0) or 0)
        dur=parse_duration_seconds(cd.get('duration',''))
        published=sn.get('publishedAt','')
        try: age=max(0.05,(now-datetime.fromisoformat(published.replace('Z','+00:00'))).total_seconds()/86400)
        except Exception: age=1
        row={
            'video_id':v['id'], 'title':sn.get('title',''), 'description':sn.get('description',''),
            'url':f"https://www.youtube.com/shorts/{v['id']}", 'channel_id':cid, 'channel_title':sn.get('channelTitle',''),
            'subscriber_count':subs, 'view_count':views, 'published_at':published, 'age_days':round(age,3), 'duration_seconds':dur,
            'thumbnail': sn.get('thumbnails',{}).get('high',{}).get('url','')
        }
        reasons=[]
        if views < CONFIG.min_views: reasons.append('below MIN_VIEWS')
        if subs > CONFIG.max_channel_subs: reasons.append('channel over MAX_CHANNEL_SUBS')
        if dur and dur > 65: reasons.append('not a Short duration')
        row['views_per_day']=round(views/age,2); row['views_per_sub']=round(views/max(1,subs),2)
        row['game']=detect_game(row); row['hook_type']=classify_hook(row['title']); row['template_type']=template_type(row); row['viral_dna']=viral_dna(row)
        ps,pv,tools,miss,why=production_score(row)
        auto_s,auto_v,tmpl,req,missing=auto_recreate(row, asset_index)
        row.update({'production_score':ps,'production_verdict':pv,'required_tools':tools,'missing_skills':miss,'why_make':why,
                    'auto_recreate_score':auto_s,'auto_recreate_verdict':auto_v,'required_inputs':req,'missing_assets':missing,
                    'opportunity_score':opportunity_score(row, ps, auto_s),'title_variants':title_variants(row)})
        row['rejection_reason']='; '.join(reasons) if reasons else ''
        processed.append(row)
        if reasons: rejected.append(row)
        else: upsert_video(con, row)
    df=pd.DataFrame(processed).sort_values('opportunity_score', ascending=False) if processed else pd.DataFrame()
    df.to_csv(out/'trend_report.csv', index=False)
    df.to_csv(out/'diagnostics'/'processed_candidates.csv', index=False)
    pd.DataFrame(rejected).to_csv(out/'diagnostics'/'rejected_candidates.csv', index=False)
    if not df.empty:
        build_sound_searches(df.to_dict('records'))
    usable=df[df['rejection_reason'].eq('')] if not df.empty else df
    usable.to_csv(out/'final_opportunities.csv', index=False)
    with open(out/'diagnostics'/'rejection_summary.md','w',encoding='utf-8') as f:
        f.write(f'# Rejection Summary\n\nRaw candidates: {len(raw)}\nProcessed: {len(processed)}\nUsable: {len(usable)}\nRejected: {len(rejected)}\n\n')
        if rejected:
            f.write(pd.Series([r['rejection_reason'] for r in rejected]).value_counts().to_markdown())
    console.print(f'[bold green]Saved {len(usable)} usable candidates.[/] {len(usable[usable.auto_recreate_verdict.eq("AUTO CREATE")]) if not usable.empty else 0} auto-create now.')
    return usable
