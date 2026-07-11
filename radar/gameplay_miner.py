from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass
import csv, json, time, shutil

BASE = Path(__file__).resolve().parents[1]
RAW = BASE / 'assets' / 'raw_gameplay'
PROCESSED = BASE / 'assets' / 'processed_gameplay'
MINED = BASE / 'assets' / 'source' / 'mined'
REPORT = BASE / 'outputs' / 'clip_miner_report.csv'
STATUS = BASE / 'outputs' / 'miner_status.json'
VIDEO_EXT = {'.mp4', '.mov', '.mkv', '.webm'}

@dataclass
class ClipHit:
    source: str
    start: float
    end: float
    score: float
    reason: str
    output: str
    user_rating: str = ""

def ensure_dirs():
    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    MINED.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)

def move_to_processed(video_path: Path):
    target = PROCESSED / video_path.name

    if target.exists():
        stem = video_path.stem
        suffix = video_path.suffix
        n = 1
        while True:
            target = PROCESSED / f"{stem}_{n}{suffix}"
            if not target.exists():
                break
            n += 1

    shutil.move(str(video_path), str(target))
    print(f"Moved to processed: {target}")


def read_existing_ratings():
    """Keep your manual ratings if the miner is run again."""
    ratings = {}
    if not REPORT.exists():
        return ratings

    try:
        with REPORT.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                output = (row.get("output") or "").replace("\\", "/")
                rating = row.get("user_rating") or ""
                if output and str(rating).strip():
                    ratings[output] = str(rating).strip()
                    ratings[Path(output).name] = str(rating).strip()
    except Exception:
        pass

    return ratings

def write_status(**data):
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        **data
    }
    STATUS.write_text(json.dumps(payload, indent=2), encoding="utf-8")

def _frame_score(clip, t: float, prev=None):
    try:
        import numpy as np
        frame = clip.get_frame(t)
        small = frame[::24, ::24, :3].astype('float32')
        bright = float(np.mean(small))
        motion = 0.0
        if prev is not None:
            motion = float(np.mean(np.abs(small - prev)))
        return small, bright, motion
    except Exception:
        return prev, 0.0, 0.0

def find_interesting_moments(path: Path, max_clips: int = 8, clip_len: float = 9.0, sample_every: float = 1.0):
    from moviepy.editor import VideoFileClip
    from tqdm import tqdm

    with VideoFileClip(str(path)) as clip:
        dur = float(clip.duration or 0)
        if dur < 6:
            return []

        prev = None
        samples = []
        steps = int(dur // sample_every)

        write_status(
            phase="analyzing",
            file=str(path),
            progress_percent=0,
            clips_found=0,
            clips_exported=0,
            message="Analyzing frames..."
        )

        for i in tqdm(range(steps), desc=f"Analyzing {path.name}", unit="sec"):
            t = i * sample_every
            prev, bright, motion = _frame_score(clip, t, prev)
            score = motion + abs(bright - 90) * 0.04
            samples.append((t, score, motion, bright))

            if i % 10 == 0:
                write_status(
                    phase="analyzing",
                    file=str(path),
                    progress_percent=round((i / max(steps, 1)) * 100, 1),
                    clips_found=0,
                    clips_exported=0,
                    message=f"Analyzing second {int(t)} / {int(dur)}"
                )

        samples = sorted(samples, key=lambda x: x[1], reverse=True)
        chosen = []

        for t, score, motion, bright in samples:
            start = max(0, t - 1.0)
            end = min(dur, start + clip_len)

            if end - start < 5:
                continue
            if any(abs(start - s) < clip_len for s, _, _, _ in chosen):
                continue

            reason = "high motion" if motion > 10 else "visual change"
            chosen.append((start, end, reason, score))

            if len(chosen) >= max_clips:
                break

        write_status(
            phase="analyzed",
            file=str(path),
            progress_percent=100,
            clips_found=len(chosen),
            clips_exported=0,
            message=f"Found {len(chosen)} interesting moments."
        )

    return sorted(chosen, key=lambda x: x[0])

def mine_raw_gameplay(max_clips_per_file: int = 8, clip_len: float = 9.0, force: bool = False):
    ensure_dirs()
    from moviepy.editor import VideoFileClip
    from tqdm import tqdm

    results = []
    existing_ratings = read_existing_ratings()
    raw_files = [p for p in RAW.rglob('*') if p.suffix.lower() in VIDEO_EXT]

    write_status(
        phase="starting",
        file=None,
        progress_percent=0,
        total_files=len(raw_files),
        clips_found=0,
        clips_exported=0,
        message=f"Found {len(raw_files)} raw gameplay files."
    )

    for file_index, p in enumerate(raw_files, start=1):
        file_failed = False

        try:
            moments = find_interesting_moments(
                p,
                max_clips=max_clips_per_file,
                clip_len=clip_len
            )

            exported = 0

            for idx, (start, end, reason, score) in enumerate(
                tqdm(moments, desc=f"Exporting {p.name}", unit="clip"),
                start=1
            ):
                out = MINED / f'{p.stem}_clip_{idx:02d}_{int(start)}s.mp4'

                if out.exists() and not force:
                    rating = existing_ratings.get(str(out).replace('\\', '/'), existing_ratings.get(out.name, ''))
                    results.append(ClipHit(str(p), start, end, score, reason, str(out), rating))
                    exported += 1
                    continue

                try:
                    write_status(
                        phase="exporting",
                        file=str(p),
                        progress_percent=round((idx / max(len(moments), 1)) * 100, 1),
                        total_files=len(raw_files),
                        current_file=file_index,
                        clips_found=len(moments),
                        clips_exported=exported,
                        message=f"Exporting clip {idx}/{len(moments)}"
                    )

                    with VideoFileClip(str(p)) as clip:
                        sub = clip.subclip(start, end)
                        sub.write_videofile(
                            str(out),
                            fps=30,
                            codec='libx264',
                            verbose=False,
                            logger=None
                        )

                    exported += 1
                    rating = existing_ratings.get(str(out).replace('\\', '/'), existing_ratings.get(out.name, ''))
                    results.append(ClipHit(str(p), start, end, score, reason, str(out), rating))

                except Exception as e:
                    file_failed = True
                    results.append(ClipHit(str(p), start, end, 0, f'failed: {e}', str(out)))

            write_status(
                phase="file_done",
                file=str(p),
                progress_percent=100,
                total_files=len(raw_files),
                current_file=file_index,
                clips_found=len(moments),
                clips_exported=exported,
                message=f"Finished {p.name}"
            )

            move_to_processed(p)

        except Exception as e:
            results.append(ClipHit(str(p), 0, 0, 0, f'failed file: {e}', ""))
            print(f"Failed scanning file, not moved: {p} -> {e}")

    with REPORT.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(
            f,
            fieldnames=['source', 'start', 'end', 'score', 'reason', 'output', 'user_rating']
        )
        w.writeheader()
        w.writerows([r.__dict__ for r in results])

    write_status(
        phase="done",
        file=None,
        progress_percent=100,
        total_files=len(raw_files),
        clips_found=len(results),
        clips_exported=len([r for r in results if not r.reason.startswith("failed")]),
        message=f"Mined {len(results)} clips. Report: {REPORT}"
    )

    return results

if __name__ == '__main__':
    hits = mine_raw_gameplay(force=False)
    print(f'Mined {len(hits)} clips. Report: {REPORT}')