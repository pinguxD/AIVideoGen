from __future__ import annotations
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta, timezone
import re
from dateutil import parser as dtparser

def iso_duration_seconds(s):
    m=re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', s or '')
    if not m: return 0
    h,mn,sec=[int(x or 0) for x in m.groups()]
    return h*3600+mn*60+sec

class YouTubeClient:
    def __init__(self, api_key):
        self.yt=build('youtube','v3',developerKey=api_key)
    def search(self, q, days_back=7, max_results=25, region='US'):
        after=(datetime.now(timezone.utc)-timedelta(days=days_back)).isoformat().replace('+00:00','Z')
        res=self.yt.search().list(part='snippet', q=q, type='video', maxResults=max_results, order='viewCount', publishedAfter=after, regionCode=region).execute()
        return res.get('items',[])
    def enrich(self, items):
        ids=[]; raw={}
        for it in items:
            vid=it.get('id',{}).get('videoId')
            if vid and vid not in raw:
                ids.append(vid); raw[vid]=it
        out=[]
        for i in range(0,len(ids),50):
            chunk=ids[i:i+50]
            vres=self.yt.videos().list(part='snippet,statistics,contentDetails', id=','.join(chunk)).execute().get('items',[])
            chids=list({v['snippet']['channelId'] for v in vres})
            chmap={}
            if chids:
                cres=self.yt.channels().list(part='statistics,snippet', id=','.join(chids)).execute().get('items',[])
                chmap={c['id']:c for c in cres}
            for v in vres:
                sn=v['snippet']; st=v.get('statistics',{}); cd=v.get('contentDetails',{})
                pub=dtparser.parse(sn.get('publishedAt'))
                age=max((datetime.now(timezone.utc)-pub).total_seconds()/86400,0.05)
                ch=chmap.get(sn['channelId'],{})
                subs=int(ch.get('statistics',{}).get('subscriberCount',0) or 0)
                out.append({
                    'video_id':v['id'], 'title':sn.get('title',''), 'description':sn.get('description',''),
                    'url':f'https://www.youtube.com/shorts/{v["id"]}', 'channel_id':sn['channelId'], 'channel_title':sn.get('channelTitle',''),
                    'subscriber_count':subs, 'view_count':int(st.get('viewCount',0) or 0), 'like_count':int(st.get('likeCount',0) or 0), 'comment_count':int(st.get('commentCount',0) or 0),
                    'published_at':sn.get('publishedAt',''), 'age_days':round(age,2), 'duration_seconds':iso_duration_seconds(cd.get('duration',''))
                })
        return out
