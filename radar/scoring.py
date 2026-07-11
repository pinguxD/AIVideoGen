from __future__ import annotations
import re, math

AUTO_TEMPLATES = {
    'guess_voice': ['guess', 'voice', 'which sound', 'real voice', '1 2 3 4'],
    'sound_replacement': ['scream', 'sound', 'funny sound', 'audio', 'voice'],
    'fact_card': ['fact', 'did you know', 'older than', 'roblox was', 'nobody knows', 'secret'],
    'choice_game': ['choose', 'pick', 'which one', 'guess', 'comment'],
    'meme_caption': ['pov', 'when ', 'bro ', 'me when', 'friend']
}

HARD_TO_CREATE = ['animation', 'animated', 'movie', 'story', 'roleplay', 'blender', 'studio animation', 'moon animator', 'roblox studio', 'custom', 'skit']
EASY_TERMS = ['guess', 'voice', 'sound', 'meme', 'fact', 'secret', 'did you know', 'pov', 'which', 'comment', 'roblox facts']
GAME_HINTS = ['animal hospital','grow a garden','99 nights','steal a brainrot','doors','pressure','forsaken','keyboard escape','fish it','slime rng','roblox']


def text_blob(v: dict) -> str:
    return ' '.join(str(v.get(k,'')) for k in ['title','description','channel_title']).lower()


def classify_hook(title: str) -> str:
    t = title.lower()
    if 'guess' in t or 'which' in t or 'real voice' in t: return 'interactive_guessing'
    if "don't" in t or 'never' in t or 'wrong' in t: return 'threat_mistake'
    if 'secret' in t or 'hidden' in t or 'nobody' in t: return 'secret_curiosity'
    if 'oldest' in t or 'older than' in t or 'remember' in t: return 'nostalgia_fact'
    if 'rare' in t or '0.0' in t or '1%' in t or '99%' in t: return 'rarity'
    if 'pov' in t: return 'pov_meme'
    return 'general_curiosity'


def detect_game(v: dict) -> str:
    blob = text_blob(v)
    for g in GAME_HINTS:
        if g in blob:
            return g.title()
    return 'Roblox'


def template_type(v: dict) -> str:
    blob = text_blob(v)
    scores = {name: sum(1 for kw in kws if kw in blob) for name,kws in AUTO_TEMPLATES.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else 'manual_review'


def production_score(v: dict) -> tuple[int, str, str, str, str]:
    blob = text_blob(v)
    score = 50
    reasons=[]; missing=[]; tools=['Roblox','CapCut']
    if any(x in blob for x in EASY_TERMS): score += 30; reasons.append('simple hook/template')
    if any(x in blob for x in HARD_TO_CREATE): score -= 45; missing.append('possible custom animation/studio work')
    tmpl = template_type(v)
    if tmpl in ['guess_voice','sound_replacement','choice_game','fact_card','meme_caption']:
        score += 20; reasons.append(f'fits {tmpl} template')
    if int(v.get('duration_seconds') or 0) and int(v.get('duration_seconds')) <= 20: score += 10; reasons.append('short format')
    if int(v.get('subscriber_count') or 0) < 10000: score += 5; reasons.append('small creator proof')
    score=max(0,min(100,score))
    verdict='MAKE' if score>=75 else ('REVIEW' if score>=50 else 'SKIP')
    why = '; '.join(reasons) if reasons else 'needs manual review'
    miss = '; '.join(missing) if missing else 'none'
    return score, verdict, ', '.join(tools), miss, why


def auto_recreate(v: dict, asset_index: dict|None=None) -> tuple[int, str, str, str, str]:
    asset_index = asset_index or {}
    tmpl = template_type(v)
    blob = text_blob(v)
    base = {'guess_voice':82,'sound_replacement':80,'fact_card':78,'choice_game':76,'meme_caption':70,'manual_review':25}[tmpl]
    missing=[]
    req=[]
    if tmpl in ['guess_voice','sound_replacement']:
        req=['source clip/image of character','3-4 meme sounds']
        if not asset_index.get('source'):
            if asset_index.get('raw_gameplay',0): missing.append('run raw gameplay miner / source clip not mined yet')
            else: missing.append('source clip/image or raw gameplay')
        if asset_index.get('sounds',0) < 3: missing.append('3+ sounds (Sound Finder can suggest/search)')
    elif tmpl=='fact_card':
        req=['background gameplay clip','fact text']
        if not asset_index.get('source'):
            if asset_index.get('raw_gameplay',0): missing.append('run raw gameplay miner / background clip not mined yet')
            else: missing.append('background gameplay or raw gameplay')
    elif tmpl=='meme_caption':
        req=['background clip/image','caption','meme sound optional']
        if not asset_index.get('source'):
            if asset_index.get('raw_gameplay',0): missing.append('run raw gameplay miner / background clip not mined yet')
            else: missing.append('background clip/image or raw gameplay')
    else:
        req=['manual review']
        missing.append('template not supported')
    if any(x in blob for x in HARD_TO_CREATE): base -= 45; missing.append('likely animation/custom scene')
    if missing: base -= min(25, len(missing)*8)
    score=max(0,min(100,base))
    verdict='AUTO CREATE' if score>=85 and not missing else ('NEEDS ASSETS' if score>=45 else 'MANUAL ONLY')
    return score, verdict, tmpl, '; '.join(req), '; '.join(missing) if missing else 'none'


def opportunity_score(v: dict, prod_score: int, auto_score: int) -> int:
    views = max(1, int(v.get('view_count') or 0))
    subs = max(1, int(v.get('subscriber_count') or 1))
    age = max(0.1, float(v.get('age_days') or 1))
    views_per_day = views/age
    views_per_sub = views/subs
    velocity = min(100, math.log10(views_per_day+10)*25)
    small_creator = min(100, math.log10(views_per_sub+1)*45)
    score = 0.35*velocity + 0.25*small_creator + 0.20*prod_score + 0.20*auto_score
    return int(max(0,min(100,score)))


def viral_dna(v: dict) -> str:
    parts=[classify_hook(v.get('title','')), template_type(v), detect_game(v)]
    dur=int(v.get('duration_seconds') or 0)
    if dur: parts.append(f'{dur}s')
    return ' + '.join(parts)


def title_variants(v: dict) -> str:
    g=detect_game(v); tmpl=template_type(v)
    if tmpl=='guess_voice':
        return f'Guess The REAL {g} Voice..., Nobody Expected This Voice..., Comment Before The Reveal...'
    if tmpl=='fact_card':
        return '99% Of Players Dont Know This..., This Roblox Fact Is Weird..., Youve Been Lied To About Roblox...'
    return 'Wait... This Is Roblox?, Nobody Expected This..., I Bet You Get This Wrong...'
