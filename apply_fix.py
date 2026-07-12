from pathlib import Path

path = Path("radar/story_scout.py")
if not path.exists():
    raise FileNotFoundError(
        "Run this script from the project root where radar/story_scout.py exists."
    )

code = path.read_text(encoding="utf-8")

needle = '        "gaming_background_score": 0,\n        "viral_score": 0,\n'
replacement = '        "gaming_background_score": 0,\n        "api_language": "",\n        "viral_score": 0,\n'
if needle in code:
    code = code.replace(needle, replacement, 1)

needle2 = '    candidates = [StoryCandidate(**row) for row in rows]\n'
replacement2 = '''    candidates = []
    for row in rows:
        row.setdefault("api_language", "")
        row.setdefault("english_confidence", 0)
        row.setdefault("detected_game", "")
        candidates.append(StoryCandidate(**row))
'''
if needle2 in code:
    code = code.replace(needle2, replacement2, 1)

path.write_text(code, encoding="utf-8")
print("Patched:", path.resolve())
