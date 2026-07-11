from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .full_video_analyzer import BASE

OUTPUT_DIR = BASE / "outputs" / "short_producer"
CREATOR_OUTPUT_DIR = BASE / "outputs" / "creator_ai_v2"


@dataclass
class ShortJob:
    job_id: str
    status: str
    source_name: str
    place_path: str
    raw_capture_path: str
    final_video_path: str
    audio_path: str
    duration: float
    created_at: float
    finished_at: float | None = None
    error: str = ""
    ffmpeg_command: list[str] | None = None

    def save(self) -> Path:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUTPUT_DIR / f"{self.job_id}.json"
        path.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path


def find_ffmpeg() -> Path:
    configured = str(os.getenv("FFMPEG_PATH") or "").strip()
    if configured:
        path = Path(configured).expanduser()
        if path.exists():
            return path.resolve()
        raise FileNotFoundError(f"FFMPEG_PATH does not exist: {path}")

    discovered = shutil.which("ffmpeg")
    if discovered:
        return Path(discovered).resolve()

    for path in (
        Path.home() / "ffmpeg" / "bin" / "ffmpeg.exe",
        Path("C:/ffmpeg/bin/ffmpeg.exe"),
        Path("C:/Program Files/ffmpeg/bin/ffmpeg.exe"),
    ):
        if path.exists():
            return path.resolve()

    raise FileNotFoundError(
        "FFmpeg was not found. Install it or set FFMPEG_PATH in .env."
    )


def latest_generated_places(limit: int = 50) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not CREATOR_OUTPUT_DIR.exists():
        return rows

    for place in CREATOR_OUTPUT_DIR.rglob("GeneratedGame.rbxlx"):
        metadata_path = place.parent / "metadata.json"
        source_name = place.parent.name
        if metadata_path.exists():
            try:
                metadata = json.loads(
                    metadata_path.read_text(encoding="utf-8")
                )
                source_name = str(metadata.get("source_name") or source_name)
            except (OSError, json.JSONDecodeError):
                pass

        rows.append(
            {
                "source_name": source_name,
                "place_path": str(place.resolve()),
                "modified": str(place.stat().st_mtime),
            }
        )

    rows.sort(key=lambda item: float(item["modified"]), reverse=True)
    return rows[: max(1, int(limit))]


def audio_candidates(limit: int = 100) -> list[dict[str, str]]:
    extensions = {".wav", ".mp3", ".m4a", ".aac", ".ogg"}
    rows: list[dict[str, str]] = []

    for folder in (BASE / "outputs", BASE / "assets" / "sounds"):
        if not folder.exists():
            continue
        for path in folder.rglob("*"):
            if path.is_file() and path.suffix.lower() in extensions:
                rows.append(
                    {
                        "name": path.name,
                        "path": str(path.resolve()),
                        "modified": str(path.stat().st_mtime),
                    }
                )

    rows.sort(key=lambda item: float(item["modified"]), reverse=True)
    return rows[: max(1, int(limit))]


def _open_place(place_path: Path) -> None:
    if not place_path.exists():
        raise FileNotFoundError(f"Generated place not found: {place_path}")

    if os.name == "nt":
        os.startfile(str(place_path))  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", str(place_path)])


def _activate_studio_and_play() -> None:
    if os.name != "nt":
        return

    script = "\n".join(
        [
            "$wshell = New-Object -ComObject WScript.Shell",
            "$activated = $false",
            'foreach ($title in @("Roblox Studio", "RobloxStudio")) {',
            "    if ($wshell.AppActivate($title)) {",
            "        $activated = $true",
            "        break",
            "    }",
            "}",
            'if (-not $activated) { throw "Roblox Studio window was not found." }',
            "Start-Sleep -Milliseconds 300",
            '$wshell.SendKeys("{F5}")',
        ]
    )

    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def _capture_command(
    ffmpeg: Path,
    raw_path: Path,
    duration: float,
    window_title: str,
) -> list[str]:
    return [
        str(ffmpeg),
        "-y",
        "-f",
        "gdigrab",
        "-framerate",
        "60",
        "-draw_mouse",
        "0",
        "-i",
        f"title={window_title}",
        "-t",
        f"{duration:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        str(raw_path),
    ]


def _render_command(
    ffmpeg: Path,
    raw_path: Path,
    final_path: Path,
    audio_path: Path | None,
    duration: float,
) -> list[str]:
    video_filter = (
        "crop='min(iw,ih*9/16)':ih:"
        "'(iw-min(iw,ih*9/16))/2':0,"
        "scale=1080:1920:flags=lanczos,"
        "fps=60,format=yuv420p"
    )

    command = [str(ffmpeg), "-y", "-i", str(raw_path)]

    if audio_path is not None:
        command.extend(
            [
                "-i",
                str(audio_path),
                "-filter_complex",
                (
                    f"[0:v]{video_filter}[v];"
                    f"[1:a]apad,atrim=0:{duration:.3f},"
                    "loudnorm=I=-14:TP=-1.5:LRA=11[a]"
                ),
                "-map",
                "[v]",
                "-map",
                "[a]",
                "-shortest",
            ]
        )
    else:
        command.extend(["-vf", video_filter, "-an"])

    command.extend(
        [
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(final_path),
        ]
    )
    return command


def produce_short(
    source_name: str,
    place_path: str,
    duration: float = 15.0,
    launch_wait: float = 12.0,
    play_wait: float = 2.0,
    window_title: str = "Roblox Studio",
    audio_path: str = "",
) -> ShortJob:
    ffmpeg = find_ffmpeg()
    place = Path(place_path).resolve()

    if duration < 3 or duration > 60:
        raise ValueError("Duration must be between 3 and 60 seconds.")

    audio: Path | None = None
    if audio_path.strip():
        audio = Path(audio_path).resolve()
        if not audio.exists():
            raise FileNotFoundError(f"Audio file not found: {audio}")

    job_id = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    raw_path = job_dir / "studio_capture.mp4"
    final_path = job_dir / "final_short_1080x1920.mp4"

    job = ShortJob(
        job_id=job_id,
        status="STARTING",
        source_name=source_name,
        place_path=str(place),
        raw_capture_path=str(raw_path),
        final_video_path=str(final_path),
        audio_path=str(audio or ""),
        duration=duration,
        created_at=time.time(),
    )
    job.save()

    try:
        _open_place(place)
        job.status = "WAITING_FOR_STUDIO"
        job.save()
        time.sleep(max(1.0, launch_wait))

        _activate_studio_and_play()
        job.status = "WAITING_FOR_PLAY"
        job.save()
        time.sleep(max(0.5, play_wait))

        capture_command = _capture_command(
            ffmpeg,
            raw_path,
            duration,
            window_title,
        )
        job.status = "RECORDING"
        job.ffmpeg_command = capture_command
        job.save()
        subprocess.run(capture_command, check=True, cwd=str(job_dir))

        render_command = _render_command(
            ffmpeg,
            raw_path,
            final_path,
            audio,
            duration,
        )
        job.status = "RENDERING"
        job.ffmpeg_command = render_command
        job.save()
        subprocess.run(render_command, check=True, cwd=str(job_dir))

        job.status = "COMPLETED"
        job.finished_at = time.time()
        job.save()
        return job

    except Exception as exc:
        job.status = "FAILED"
        job.error = str(exc)
        job.finished_at = time.time()
        job.save()
        raise


def list_jobs(limit: int = 100) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not OUTPUT_DIR.exists():
        return rows

    for path in OUTPUT_DIR.glob("*.json"):
        try:
            rows.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue

    rows.sort(
        key=lambda item: float(item.get("created_at") or 0),
        reverse=True,
    )
    return rows[: max(1, int(limit))]
