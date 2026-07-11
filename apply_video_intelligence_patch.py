from __future__ import annotations

import shutil
from pathlib import Path

PATCH_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = Path.cwd()


def copy_files() -> None:
    for source in (PATCH_ROOT / "radar").glob("*.py"):
        target = PROJECT_ROOT / "radar" / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        print(f"Copying:\n  FROM: {source}\n  TO:   {target}", flush=True)
        shutil.copy2(source, target)
        print(f"Updated {target.relative_to(PROJECT_ROOT)}")


def patch_app() -> None:
    app_path = PROJECT_ROOT / "app.py"
    text = app_path.read_text(encoding="utf-8")

    nav_marker = '("/recommendations", "Recommended Shorts"),'
    nav_line = '("/classification-review", "Classification Review"),'
    if nav_line not in text:
        if nav_marker in text:
            text = text.replace(nav_marker, nav_marker + "\n    " + nav_line, 1)
        else:
            print("Warning: could not automatically add Classification Review to NAV_ITEMS")

    registration = '''\n# Video classification review routes\nfrom radar.classification_web import register_classification_routes\nregister_classification_routes(app, BASE, page, esc, load_recommendations)\n'''
    if "register_classification_routes" not in text:
        marker = "# Creator AI routes"
        if marker in text:
            text = text.replace(marker, registration + "\n" + marker, 1)
        elif 'if __name__ == "__main__":' in text:
            text = text.replace('if __name__ == "__main__":', registration + '\nif __name__ == "__main__":', 1)
        else:
            raise RuntimeError("Could not find a safe insertion point in app.py")

    app_path.write_text(text, encoding="utf-8")
    print("Patched app.py")


def patch_creator_projects() -> None:
    path = PROJECT_ROOT / "radar" / "creator_projects.py"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")

    # Ensure low-confidence/manual-review scanner rows cannot become auto-ready projects.
    old = 'template = _normalise_template(str(video.get("template_type") or ""), title)'
    new = '''template = _normalise_template(str(video.get("template_type") or ""), title)\n    classification_review = str(video.get("classification_needs_review", "")).lower() in {"true", "1", "yes"}\n    if classification_review:\n        template = "manual"'''
    if old in text and "classification_review =" not in text:
        text = text.replace(old, new, 1)
        path.write_text(text, encoding="utf-8")
        print("Patched radar/creator_projects.py")


def main() -> None:
    if not (PROJECT_ROOT / "app.py").exists() or not (PROJECT_ROOT / "radar").exists():
        raise SystemExit("Run this script from the AIVideoGen project root.")
    copy_files()
    patch_app()
    patch_creator_projects()
    print("\nVideo Intelligence v1 installed. Restart with: py app.py")


if __name__ == "__main__":
    main()
