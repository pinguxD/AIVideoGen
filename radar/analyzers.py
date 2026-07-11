from __future__ import annotations
import re, math, json
from radar.assets import find_assets

GAMES = ['animal hospital','grow a garden','steal a brainrot','99 nights','doors','pressure','forsaken','fish it','keyboard escape','roblox']
CHARACTERS = ['intern','duckman','doctor','monster','nurse','patient','janitor','bear','brainrot']

def norm(s): return (s or '').lower()

def detect_game(title, desc=''):
    text=norm(title+' '+desc)
    for g in GAMES:
        if g in text: return g.title()
    return 'Roblox'

def detect_character(title, desc=''):
    text=norm(title+' '+desc)
    for c in CHARACTERS:
        if c in text: return c.title()
    return ''

def hook_type(title):
    t=norm(title)
    if any(x in t for x in ['guess','which one','real voice','real sound']): return 'interactive_guess'
    if any(x in t for x in ['don\'t','never','avoid','wrong','ruin']): return 'threat/mistake'
    if any(x in t for x in ['secret','hidden','nobody','rare','oldest','only 1','99%']): return 'curiosity/secret'
    if any(x in t for x in ['how to','tips','guide','beat']): return 'guide/tutorial'
    if any(x in t for x in ['update','new','leaked']): return 'news/update'
    if any(x in t for x in ['funny','meme','what the','sound']): return 'meme/funny'
    return 'unknown'

def template_type(title):
    t=norm(title)
    if 'guess' in t and any(x in t for x in ['voice','sound']): return 'Guess The Voice/Sound'
    if any(x in t for x in ['voice','sound']) and any(x in t for x in ['real','leaked']): return 'Voice Reveal'
    if any(x in t for x in ['fact','oldest','wasn\'t','called','roblox was']): return 'Roblox Fact'
    if any(x in t for x in ['don\'t','wrong','ruin']): return 'Mistake Warning'
    if any(x in t for x in ['secret','hidden','nobody']): return 'Secret Reveal'
    if any(x in t for x in ['funny','meme']): return 'Meme Caption'
    return 'General Short'

def production_analysis(v):
    title=norm(v.get('title',''))
    tmpl=template_type(title)
    score=55; minutes=25; tools=['Roblox','CapCut']; missing=[]; why=[]; why_not=[]
    # boosts for Arno workflow
    if tmpl in ['Guess The Voice/Sound','Voice Reveal']:
        score += 35; minutes=10; tools += ['Funny sounds']; why.append('Interactive guessing format matches your successful Intern Voice video.')
    if tmpl in ['Roblox Fact','Mistake Warning','Secret Reveal']:
        score += 20; minutes=min(minutes,18); why.append('Simple hook + footage format fits your current workflow.')
    if 'animation' in title or 'animated' in title or 'movie' in title:
        score -= 35; minutes += 90; missing.append('Animation workflow'); why_not.append('May require custom animation instead of normal gameplay capture.')
    if any(x in title for x in ['blender','moon animator','studio animation']):
        score -= 50; minutes += 120; missing += ['Blender/Moon Animator']; why_not.append('Requires specialist animation tools.')
    if any(x in title for x in ['roleplay','skit']):
        score -= 10; minutes += 20; missing.append('Acting/roleplay setup')
    score=max(0,min(100,score))
    verdict='MAKE' if score>=80 else ('REVIEW' if score>=60 else 'SKIP')
    return {
        'production_score':score,'production_verdict':verdict,'production_minutes':minutes,
        'required_tools':tools,'missing_skills':sorted(set(missing)),
        'why_make':' '.join(why) or 'Potentially usable Roblox Short format.',
        'why_not':' '.join(why_not)
    }

def auto_studio_analysis(v, assets):
    title=norm(v.get('title',''))
    tmpl=template_type(title)
    game=detect_game(title, v.get('description',''))
    char=detect_character(title, v.get('description',''))
    required=[]; missing=[]; found=[]; score=10; status='MANUAL_ONLY'; verdict='NO'
    blueprint={'template':tmpl,'steps':[]}
    if tmpl in ['Guess The Voice/Sound','Voice Reveal']:
        score=82; status='NEEDS_ASSETS'; verdict='NEEDS ASSETS'
        keywords=[k for k in [game.lower(), char.lower() if char else '', 'monster','intern','duckman'] if k]
        src=find_assets(assets, keywords, kind='source', min_count=1)
        sounds=[a['path'] for a in assets if a['type']=='sound'][:4]
        required=['1 source clip or image of the character/game','3-4 funny sounds']
        if src: found += src
        else: missing.append(f'Add 1 source clip/image for {char or game}')
        if len(sounds)>=3: found += sounds[:4]
        else: missing.append(f'Add {3-len(sounds)} more funny sounds to assets/sounds')
        if not missing:
            score=96; status='AUTO_CREATE'; verdict='AUTO CREATE'
        blueprint={'template':'guess_voice','steps':['0.0s hook text: Guess the REAL voice','1-6s play options/sounds','6-9s reveal','hard cut for loop'], 'suggested_title': f'Guess the REAL {char or "Roblox"} Voice...'}
    elif tmpl in ['Roblox Fact','Mistake Warning','Secret Reveal','Meme Caption']:
        score=65; status='NEEDS_ASSETS'; verdict='NEEDS ASSETS'
        src=[a['path'] for a in assets if a['type']=='source'][:1]
        required=['1 background gameplay clip/image','caption text']
        if src: found+=src; score=88; status='AUTO_CREATE'; verdict='AUTO CREATE'
        else: missing.append('Add 1 background gameplay clip/image to assets/source')
        blueprint={'template':'caption_over_gameplay','steps':['0.0s big curiosity caption','0-8s background footage','8-11s reveal/payoff','loop ending']}
    return {
        'auto_recreate_score':max(0,min(100,score)), 'auto_recreate_verdict':verdict,
        'auto_status':status,'required_inputs':required,'found_assets':found,'missing_assets':missing,
        'template_blueprint':blueprint
    }

def opportunity(v):
    views=v.get('view_count',0) or 0; subs=max(v.get('subscriber_count',0) or 0,1); age=max(v.get('age_days',1) or 1,0.1)
    vpd=views/age; vps=views/subs
    prod=v.get('production_score',0); auto=v.get('auto_recreate_score',0)
    score = 0.28*min(100, math.log10(max(vpd,1))*22) + 0.25*min(100, math.log10(max(vps,1))*35) + 0.25*prod + 0.15*auto + 7
    return int(max(0,min(100,score)))

def analyze(v, assets):
    v=dict(v)
    title=v.get('title','')
    v['game']=detect_game(title, v.get('description',''))
    v['character']=detect_character(title, v.get('description',''))
    v['hook_type']=hook_type(title)
    v['template_type']=template_type(title)
    age=max(v.get('age_days',0.1),0.1); subs=max(v.get('subscriber_count',0) or 1,1)
    v['views_per_day']=round((v.get('view_count',0) or 0)/age,2)
    v['views_per_sub']=round((v.get('view_count',0) or 0)/subs,2)
    v.update(production_analysis(v))
    v.update(auto_studio_analysis(v, assets))
    v['viral_dna']={'game':v['game'],'hook':v['hook_type'],'template':v['template_type'],'interactive':v['hook_type']=='interactive_guess','simple_edit':v['production_score']>=75}
    v['title_variants']=[title, title.replace('Guess','Can You Guess') if 'Guess' in title else f'Nobody Expected This... 😭', f'{v["game"]} Players Need To See This...']
    v['opportunity_score']=opportunity(v)
    v['rejection_reason']='' if v['production_score']>=40 else 'Low production fit'
    return v
