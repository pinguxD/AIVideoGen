from __future__ import annotations
from googleapiclient.discovery import build
from datetime import datetime, timedelta, timezone
import isodate

class YouTubeClient:
    def __init__(self, api_key: str):
        if not api_key: raise ValueError('Missing YOUTUBE_API_KEY in .env')
        self.yt=build('youtube','v3',developerKey=api_key)

    def search(self, query: str, days_back=7, max_results=20, region_code='US'):
        published_after=(datetime.now(timezone.utc)-timedelta(days=days_back)).isoformat()
        req=self.yt.search().list(part='snippet', q=query, type='video', videoDuration='short', order='viewCount', maxResults=min(50,max_results), publishedAfter=published_after, regionCode=region_code, safeSearch='none')
        res=req.execute()
        return res.get('items',[])

    def videos(self, ids):
        if not ids: return []
        out=[]
        for i in range(0,len(ids),50):
            res=self.yt.videos().list(part='snippet,statistics,contentDetails', id=','.join(ids[i:i+50])).execute()
            out += res.get('items',[])
        return out

    def channels(self, ids):
        if not ids: return {}
        out={}
        ids=list(set(ids))
        for i in range(0,len(ids),50):
            res=self.yt.channels().list(part='snippet,statistics', id=','.join(ids[i:i+50])).execute()
            for c in res.get('items',[]):
                out[c['id']]=c
        return out


def parse_duration_seconds(iso: str) -> int:
    try: return int(isodate.parse_duration(iso).total_seconds())
    except Exception: return 0
