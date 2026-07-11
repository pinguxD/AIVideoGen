from __future__ import annotations
from pathlib import Path
from .assets import scan_assets
import textwrap, random, shutil

DRAFTS=Path('outputs/drafts')

def generate_blueprint(video: dict) -> Path:
    DRAFTS.mkdir(parents=True, exist_ok=True)
    vid=video.get('video_id','draft')
    path=DRAFTS/f'{vid}_blueprint.md'
    template=video.get('template_type','manual')
    lines=[f"# Auto Studio Blueprint: {video.get('title','')}", '', f"Source inspiration: {video.get('url','')}", f"Template: {template}", f"Auto Verdict: {video.get('auto_recreate_verdict','')}", f"Missing assets: {video.get('missing_assets','')}", '']
    if template=='guess_voice':
        lines += ['## Timeline', '0.0s Big text: GUESS THE REAL VOICE', '0.8s Option 1 sound', '2.2s Option 2 sound', '3.6s Option 3 sound', '5.0s Option 4 sound', '6.5s Text: Comment before reveal', '8.0s Reveal sound + zoom', '9.5s Hard cut / loop']
    elif template=='sound_replacement':
        lines += ['## Timeline','0.0s Character opens mouth / monster scream moment','0.2s Text: Guess the REAL scream','1-6s Play fake sounds','7s Reveal funniest sound','8s Cut instantly']
    elif template=='fact_card':
        lines += ['## Timeline','0.0s Curiosity fact hook','1-6s Background gameplay + fast captions','7-10s Reveal/payoff','End with loop or question']
    else:
        lines += ['## Manual review needed','This template is not fully automated yet.']
    lines += ['', '## Suggested titles', video.get('title_variants',''), '', '## Assets needed', video.get('required_inputs','')]
    path.write_text('\n'.join(lines), encoding='utf-8')
    return path


def generate_simple_draft(video: dict) -> Path:
    """Creates a blueprint always; if moviepy and assets exist, also attempts a simple 9:16 mp4."""
    bp=generate_blueprint(video)
    try:
        from moviepy.editor import VideoFileClip, ImageClip, AudioFileClip, CompositeVideoClip, TextClip, concatenate_audioclips
        assets=scan_assets(); sources=assets['source_files']; sounds=assets['sound_files']
        if not sources: return bp
        source=Path(sources[0]); out=DRAFTS/f"{video.get('video_id','draft')}_draft.mp4"
        duration=10
        if source.suffix.lower() in ['.png','.jpg','.jpeg','.webp']:
            clip=ImageClip(str(source)).set_duration(duration)
        else:
            clip=VideoFileClip(str(source)).subclip(0, min(duration, VideoFileClip(str(source)).duration)).without_audio()
        clip=clip.resize(height=1920) if clip.h < 1920 else clip
        clip=clip.crop(x_center=clip.w/2, y_center=clip.h/2, width=1080, height=1920)
        txt=TextClip('GUESS THE REAL VOICE', fontsize=80, color='white', stroke_color='black', stroke_width=4).set_position(('center',120)).set_duration(duration)
        final=CompositeVideoClip([clip, txt])
        if sounds:
            audio_clips=[]
            for s in sounds[:4]:
                a=AudioFileClip(str(s)).subclip(0, min(1.5, AudioFileClip(str(s)).duration))
                audio_clips.append(a)
            if audio_clips:
                final=final.set_audio(concatenate_audioclips(audio_clips))
        final.write_videofile(str(out), fps=30, codec='libx264', audio_codec='aac', verbose=False, logger=None)
        return out
    except Exception:
        return bp
