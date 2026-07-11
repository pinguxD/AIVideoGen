from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGET = Path.cwd()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        print(f"[skip] {label}: pattern not found (may already be patched)")
        return text
    print(f"[ok] {label}")
    return text.replace(old, new, 1)


def patch_creator_projects() -> None:
    path = TARGET / "radar" / "creator_projects.py"
    text = path.read_text(encoding="utf-8")

    import_line = "from .clip_brain import choose_clips_for_project\n"
    if import_line not in text:
        marker = "from .channel_feedback import classify_hook, personal_multiplier\n"
        text = replace_once(text, marker, marker + import_line, "creator_projects import Clip Brain")

    # Add persistent project fields if the local version does not have them yet.
    field_marker = '    notes: list[str] = field(default_factory=list)\n'
    extra_fields = (
        '    character_name: str = ""\n'
        '    correct_answer: int = 1\n'
        '    approved: bool = False\n'
        '    approval_notes: str = ""\n'
        '    clip_match_score: float = 0.0\n'
        '    clip_match_reasons: list[str] = field(default_factory=list)\n'
        '    clip_match_warnings: list[str] = field(default_factory=list)\n'
        '    recording_task: str = ""\n'
    )
    if "clip_match_score:" not in text:
        text = replace_once(text, field_marker, field_marker + extra_fields, "CreatorProject Clip Brain fields")

    old = """    clip_count = 5 if template == \"guess_voice\" else 1
    clips = _choose_clips(clip_count)
"""
    new = """    clip_count = 5 if template == \"guess_voice\" else 1
    character_match = re.search(r\"(?:real\\s+)?([a-z0-9 _-]{2,30}?)\\s+(?:voice|sound|scream)\", title, re.I)
    character_name = character_match.group(1).strip() if character_match else \"\"
    clips, clip_matches, clip_requirements, recording_task = choose_clips_for_project(
        title=title,
        template_type=template,
        character_name=character_name,
        count=clip_count,
    )
"""
    text = replace_once(text, old, new, "context-aware clip selection")

    # Guess Voice now uses one relevant source asset, not four unrelated assets.
    text = text.replace(
        '    if template == "guess_voice" and len(clips) < 4:\n        missing.append(f"{4 - len(clips)} more distinct gameplay clips")\n',
        '    if template == "guess_voice" and len(clips) < 1:\n        missing.append("one relevant character/gameplay clip")\n',
    )

    constructor_marker = """        notes=[
            "Creator AI selected distinct clips ranked by your ratings and miner score.",
"""
    constructor_new = """        character_name=character_name,
        clip_match_score=clip_matches[0].score if clip_matches else 0.0,
        clip_match_reasons=clip_matches[0].reasons if clip_matches else [],
        clip_match_warnings=clip_matches[0].warnings if clip_matches else [],
        recording_task=recording_task,
        notes=[
            "Clip Brain selected assets against the inspiration requirements, your ratings, and project feedback.",
"""
    text = replace_once(text, constructor_marker, constructor_new, "store match explanation")

    # Normalize old project JSON safely.
    if "def _normalise_project_data(" not in text:
        insertion = '''\n\ndef _normalise_project_data(data: dict[str, Any]) -> dict[str, Any]:\n    defaults = {\n        "source_clip": "", "source_clips": [], "sounds": [], "sound_queries": [],\n        "text_lines": [], "missing": [], "output_file": "", "notes": [],\n        "character_name": "", "correct_answer": 1, "approved": False,\n        "approval_notes": "", "clip_match_score": 0.0,\n        "clip_match_reasons": [], "clip_match_warnings": [], "recording_task": "",\n    }\n    for key, value in defaults.items():\n        data.setdefault(key, value.copy() if isinstance(value, list) else value)\n    if not data.get("source_clips") and data.get("source_clip"):\n        data["source_clips"] = [data["source_clip"]]\n    allowed = set(CreatorProject.__dataclass_fields__)\n    return {key: value for key, value in data.items() if key in allowed}\n'''
        marker = "\ndef load_projects() -> list[CreatorProject]:\n"
        text = replace_once(text, marker, insertion + marker, "project JSON normalizer")

    text = text.replace("projects.append(CreatorProject(**data))", "projects.append(CreatorProject(**_normalise_project_data(data)))")
    text = text.replace("return CreatorProject(**data)", "return CreatorProject(**_normalise_project_data(data))")
    path.write_text(text, encoding="utf-8")


def patch_creator_web() -> None:
    path = TARGET / "radar" / "creator_web.py"
    text = path.read_text(encoding="utf-8")

    import_line = "from .clip_brain import save_feedback\n"
    if import_line not in text:
        marker = "from .template_renderer import render_project\n"
        text = replace_once(text, marker, marker + import_line, "creator_web feedback import")

    # Add match details to card when exact readable string is present.
    old = """              <p><b>Selected clip:</b> <span class=\"path\">{esc(p.source_clip or 'missing')}</span></p>
"""
    new = """              <p><b>Selected clip:</b> <span class=\"path\">{esc(p.source_clip or 'missing')}</span></p>
              <p><b>Clip match:</b> {p.clip_match_score:.1f}%</p>
              {f'<p class="warn"><b>Recording task:</b> {esc(p.recording_task)}</p>' if p.recording_task else ''}
"""
    text = replace_once(text, old, new, "project card match score")

    # Insert contextual controls after source clip preview section.
    marker = """        sound_cards = []
"""
    feedback_block = '''        clip_feedback = ""\n        if p.source_clip:\n            buttons = [\n                ("fits", "Fits project"),\n                ("does_not_fit", "Doesn't fit"),\n                ("wrong_character", "Wrong character"),\n                ("wrong_action", "Wrong action"),\n                ("character_not_visible", "Character not visible"),\n                ("too_much_ui", "Too much UI"),\n                ("poor_framing", "Poor framing"),\n                ("never_use", "Never use clip"),\n            ]\n            clip_feedback = '<div class="card"><h3>Clip feedback</h3><p>Teach Clip Brain why this asset fits or fails this specific inspiration.</p><div class="row-actions">' + ''.join(\n                f'<form method="post" action="/creator-ai/clip-feedback/{esc(p.video_id)}/{action}"><button>{esc(label)}</button></form>'\n                for action, label in buttons\n            ) + '</div></div>'\n\n'''
    if "clip_feedback =" not in text:
        text = replace_once(text, marker, feedback_block + marker, "project clip feedback controls")

    body_marker = """        <h3>Final settings</h3>
"""
    if body_marker in text and "{clip_feedback}" not in text:
        text = replace_once(text, body_marker, "        {clip_feedback}\n" + body_marker, "display feedback controls")

    route_marker = '    @app.route("/creator-ai/approve/<video_id>", methods=["POST"])\n'
    route_code = '''    @app.route("/creator-ai/clip-feedback/<video_id>/<action>", methods=["POST"])\n    def creator_clip_feedback(video_id: str, action: str):\n        allowed = {\n            "fits", "does_not_fit", "wrong_character", "wrong_action",\n            "character_not_visible", "too_much_ui", "poor_framing", "never_use",\n        }\n        if action not in allowed:\n            return "Unknown feedback action", 400\n        p = load_project(video_id)\n        if not p.source_clip:\n            return "Project has no selected clip", 400\n        save_feedback(\n            clip_path=p.source_clip,\n            video_id=p.video_id,\n            template_type=p.template_type,\n            character_name=p.character_name,\n            action=action,\n            reason=str(request.form.get("reason") or "").strip(),\n        )\n        p.approved = False\n        p.status = "READY_FOR_APPROVAL"\n        p.save()\n        return redirect(f"/creator-ai/project/{video_id}")\n\n'''
    if "def creator_clip_feedback(" not in text:
        text = replace_once(text, route_marker, route_code + route_marker, "clip feedback route")

    path.write_text(text, encoding="utf-8")


def patch_miner_defaults() -> None:
    path = TARGET / "radar" / "gameplay_miner.py"
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"def find_interesting_moments\(path: Path, max_clips: int = \d+", "def find_interesting_moments(path: Path, max_clips: int = 30", text)
    text = re.sub(r"def mine_raw_gameplay\(max_clips_per_file: int = \d+", "def mine_raw_gameplay(max_clips_per_file: int = 30", text)
    path.write_text(text, encoding="utf-8")
    print("[ok] miner defaults set to 30 clips per source")


def copy_new_module() -> None:
    source = ROOT / "radar" / "clip_brain.py"
    destination = TARGET / "radar" / "clip_brain.py"
    destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    print("[ok] added radar/clip_brain.py")


if __name__ == "__main__":
    if not (TARGET / "radar").exists():
        raise SystemExit("Run this script from the AIVideoGen project root.")
    copy_new_module()
    patch_creator_projects()
    patch_creator_web()
    patch_miner_defaults()
    print("\nClip Brain v1 applied. Restart with: py app.py")
