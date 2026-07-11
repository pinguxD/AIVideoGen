from __future__ import annotations

import json
import re
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

from .creator_projects import BASE, DRAFT_DIR, CreatorProject
from .sound_library import attribution_text, load_index


def safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value)).lstrip("-").strip("._")
    return cleaned or "video"


def _font(size: int):
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/impact.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _text_image(text: str, size: tuple[int, int] = (1080, 340), font_size: int = 76) -> Image.Image:
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    font = _font(font_size)
    lines = "\n".join(textwrap.wrap(str(text), width=24) or [str(text)])
    box = draw.multiline_textbbox((0, 0), lines, font=font, stroke_width=5, align="center")
    x = (size[0] - (box[2] - box[0])) / 2
    y = (size[1] - (box[3] - box[1])) / 2
    draw.multiline_text((x, y), lines, font=font, fill="white", stroke_width=5, stroke_fill="black", align="center")
    return canvas


def _load_project(video_id: str) -> CreatorProject:
    path = BASE / "outputs" / "creator_projects" / f"{video_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Project not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("source_clips", [data.get("source_clip", "")] if data.get("source_clip") else [])
    data.setdefault("correct_answer", 3)
    data.setdefault("approved", False)
    data.setdefault("character_name", "Character")
    data.setdefault("approval_notes", "")
    return CreatorProject(**data)


def _asset_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else BASE / path


def _vertical_clip(path: Path, duration: float, start_time: float = 0.0):
    from moviepy.editor import VideoFileClip, vfx

    source = VideoFileClip(str(path))
    source_duration = float(source.duration or 0)
    if source_duration <= 0:
        source.close()
        raise RuntimeError(f"Video has no usable duration: {path}")

    safe_start = max(0.0, min(float(start_time), max(0.0, source_duration - 0.1)))
    available = source_duration - safe_start
    if available >= duration:
        clip = source.subclip(safe_start, safe_start + duration)
    else:
        clip = source.subclip(safe_start).fx(vfx.loop, duration=duration)

    target_ratio = 1080 / 1920
    current_ratio = clip.w / clip.h
    if current_ratio > target_ratio:
        clip = clip.crop(x_center=clip.w / 2, width=int(clip.h * target_ratio))
    else:
        clip = clip.crop(y_center=clip.h / 2, height=int(clip.w / target_ratio))
    return clip.resize((1080, 1920)).without_audio()


def _image_clip(image: Image.Image, start: float, duration: float, y: int):
    import numpy as np
    from moviepy.editor import ImageClip
    return ImageClip(np.array(image)).set_start(start).set_duration(duration).set_position((0, y))


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(v) for v in values if v))


def _normalized_audio(path: Path, max_duration: float, start: float):
    from moviepy.editor import AudioFileClip
    from moviepy.audio.fx.all import audio_normalize

    audio = AudioFileClip(str(path))
    duration = min(max_duration, float(audio.duration or 0))
    if duration <= 0:
        audio.close()
        raise RuntimeError(f"Sound has no usable duration: {path}")
    normalized = audio.subclip(0, duration).fx(audio_normalize).set_start(start)
    return audio, normalized


def render_project(video_id: str) -> Path:
    from moviepy.editor import CompositeAudioClip, CompositeVideoClip, concatenate_videoclips

    project = _load_project(video_id)
    if project.status != "AUTO_READY" or not project.approved:
        raise RuntimeError("Project must be reviewed and approved before rendering.")

    sounds = _unique(project.sounds)
    clips = _unique(project.source_clips or ([project.source_clip] if project.source_clip else []))

    if project.template_type == "guess_voice":
        if len(sounds) < 4:
            raise RuntimeError(f"Guess Voice needs 4 unique sounds; found {len(sounds)}.")
        if not clips:
            raise RuntimeError("Guess Voice needs at least one gameplay clip.")

    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    safe_id = safe_filename(video_id)
    safe_template = safe_filename(project.template_type)
    output = (DRAFT_DIR / f"{safe_id}_{safe_template}.mp4").resolve()
    temp_audio = (DRAFT_DIR / f"{safe_id}_{safe_template}_temp_audio.m4a").resolve()
    credits = (DRAFT_DIR / f"{safe_id}_{safe_template}_sound_credits.txt").resolve()

    opened = []
    try:
        if project.template_type == "guess_voice":
            source_path = _asset_path(clips[0])
            if not source_path.exists():
                raise FileNotFoundError(f"Clip not found: {source_path}")

            hook_duration = 0.55
            option_duration = 1.20
            prompt_duration = 0.85
            reveal_duration = 1.85
            option_starts = [hook_duration + i * option_duration for i in range(4)]
            prompt_start = hook_duration + 4 * option_duration
            reveal_start = prompt_start + prompt_duration
            source_offsets = [0.4, 1.8, 3.2, 4.6]

            visual_segments = []
            audio_layers = []
            headline = project.text_lines[0] if project.text_lines else "GUESS THE REAL VOICE"

            hook = _vertical_clip(source_path, hook_duration, 0.0)
            opened.append(hook)

            overlays = [_image_clip(_text_image(headline), 0, reveal_start, 50)]

            for idx in range(4):
                segment = _vertical_clip(source_path, option_duration, source_offsets[idx])
                if idx == 1:
                    segment = segment.fl_image(lambda frame: frame[:, ::-1])
                elif idx == 2:
                    segment = segment.resize(1.06).crop(x_center=540, y_center=960, width=1080, height=1920)
                elif idx == 3:
                    segment = segment.resize(1.12).crop(x_center=540, y_center=960, width=1080, height=1920)
                opened.append(segment)
                visual_segments.append(segment)

                sound_path = _asset_path(sounds[idx])
                if not sound_path.exists():
                    raise FileNotFoundError(f"Sound not found: {sound_path}")
                raw_audio, layer = _normalized_audio(sound_path, option_duration - 0.08, option_starts[idx] + 0.05)
                opened.append(raw_audio)
                audio_layers.append(layer)

                label = project.text_lines[idx + 1] if idx + 1 < len(project.text_lines) else str(idx + 1)
                overlays.append(_image_clip(_text_image(label, (1080, 220), 145), option_starts[idx], option_duration, 1120))

            prompt = _vertical_clip(source_path, prompt_duration, 6.0)
            opened.append(prompt)
            reveal = _vertical_clip(source_path, reveal_duration, 7.0).resize(1.12).crop(
                x_center=540, y_center=960, width=1080, height=1920
            )
            opened.append(reveal)

            sequence = concatenate_videoclips([hook, *visual_segments, prompt, reveal], method="compose")
            total_duration = float(sequence.duration)

            overlays.append(_image_clip(_text_image("COMMENT YOUR ANSWER", (1080, 260), 64), prompt_start, prompt_duration, 1350))
            overlays.append(_image_clip(_text_image(f"THE REAL VOICE IS {project.correct_answer}", (1080, 280), 76), reveal_start, reveal_duration, 1120))

            correct_index = max(0, min(3, int(project.correct_answer) - 1))
            correct_path = _asset_path(sounds[correct_index])
            raw_correct, correct_layer = _normalized_audio(correct_path, reveal_duration - 0.12, reveal_start + 0.08)
            opened.append(raw_correct)
            audio_layers.append(correct_layer)

            final = CompositeVideoClip([sequence, *overlays], size=(1080, 1920)).set_duration(total_duration)
            final = final.set_audio(CompositeAudioClip(audio_layers))

        elif project.template_type == "sound_replacement":
            if not clips or not sounds:
                raise RuntimeError("Sound replacement needs one clip and one sound.")
            base = _vertical_clip(_asset_path(clips[0]), 8.0, 0.0)
            opened.append(base)
            raw_audio, audio = _normalized_audio(_asset_path(sounds[0]), 7.5, 0.25)
            opened.append(raw_audio)
            headline = project.text_lines[0] if project.text_lines else "WAIT FOR THE SOUND"
            final = CompositeVideoClip([
                base,
                _image_clip(_text_image(headline), 0, 8.0, 80),
            ], size=(1080, 1920)).set_duration(8.0).set_audio(audio)

        elif project.template_type == "fact_card":
            if not clips:
                raise RuntimeError("Fact card needs one gameplay clip.")
            base = _vertical_clip(_asset_path(clips[0]), 10.0, 0.0)
            opened.append(base)
            headline = project.text_lines[0] if project.text_lines else project.inspiration_title
            final = CompositeVideoClip([
                base,
                _image_clip(_text_image(headline), 0, 10.0, 80),
            ], size=(1080, 1920)).set_duration(10.0)
        else:
            raise RuntimeError(f"Unsupported template: {project.template_type}")

        opened.append(final)
        final.write_videofile(
            str(output), fps=30, codec="libx264", audio_codec="aac",
            temp_audiofile=str(temp_audio), remove_temp=True,
            preset="medium", threads=4, verbose=False, logger=None,
        )
        project.output_file = str(output.relative_to(BASE)).replace("\\", "/")
        project.save()

        sound_index = {item.file: item for item in load_index()}
        sound_items = [sound_index[value] for value in sounds if value in sound_index]
        credits.write_text(attribution_text(sound_items), encoding="utf-8")
        return output
    finally:
        for item in reversed(opened):
            try:
                item.close()
            except Exception:
                pass
