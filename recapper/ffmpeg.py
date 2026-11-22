"""FFmpeg/ffprobe utilities.

Shared helpers for availability checks, probing, and command execution.
Task 3 will extend this with full render command runners and temp workspace
management.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import shutil
import subprocess


class FFmpegError(RuntimeError):
    pass


@dataclass
class CommandResult:
    cmd: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def which(cmd: str) -> str | None:
    return shutil.which(cmd)


def check_system() -> dict[str, Any]:
    ffmpeg_path = which("ffmpeg")
    ffprobe_path = which("ffprobe")
    result: dict[str, Any] = {
        "ffmpeg": {"available": bool(ffmpeg_path), "path": ffmpeg_path},
        "ffprobe": {"available": bool(ffprobe_path), "path": ffprobe_path},
        "ok": bool(ffmpeg_path and ffprobe_path),
    }
    if ffmpeg_path:
        r = run_command([ffmpeg_path, "-version"])
        first = (r.stdout or r.stderr).splitlines()[0] if (r.stdout or r.stderr) else ""
        result["ffmpeg"]["version"] = first
    if ffprobe_path:
        r = run_command([ffprobe_path, "-version"])
        first = (r.stdout or r.stderr).splitlines()[0] if (r.stdout or r.stderr) else ""
        result["ffprobe"]["version"] = first
    if not result["ok"]:
        result["error"] = (
            "ffmpeg and ffprobe are required. Install FFmpeg and ensure both commands are on PATH."
        )
    return result


def run_command(cmd: list[str], timeout: int | None = None) -> CommandResult:
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as e:
        raise FFmpegError(f"Command not found: {cmd[0]}") from e
    except subprocess.TimeoutExpired as e:
        raise FFmpegError(f"Command timed out: {' '.join(cmd)}") from e
    return CommandResult(cmd=cmd, returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)


def probe_media(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Media file not found: {p}")
    ffprobe_path = which("ffprobe")
    if not ffprobe_path:
        raise FFmpegError("ffprobe not found on PATH")

    cmd = [
        ffprobe_path,
        "-v",
        "error",
        "-show_format",
        "-show_streams",
        "-of",
        "json",
        str(p),
    ]
    r = run_command(cmd)
    if r.returncode != 0:
        raise FFmpegError(f"ffprobe failed for {p}: {r.stderr.strip()}")

    try:
        raw = json.loads(r.stdout or "{}")
    except json.JSONDecodeError as e:
        raise FFmpegError(f"Invalid ffprobe output for {p}") from e

    streams = raw.get("streams", []) or []
    fmt = raw.get("format", {}) or {}
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

    duration = None
    for src in (fmt.get("duration"), video.get("duration") if video else None, audio.get("duration") if audio else None):
        if src is not None:
            try:
                duration = float(src)
                break
            except (TypeError, ValueError):
                pass

    media_type = "audio" if audio and not video else "video" if video else "image"
    # Still images often show up as video stream; detect common image formats.
    fmt_name = (fmt.get("format_name") or "").lower()
    if video and not audio and any(x in fmt_name for x in ["image", "jpeg", "png", "webp", "gif", "bmp", "tiff"]):
        media_type = "image"
        # For images, duration is not meaningful unless looped.
        duration = duration if duration and duration > 0 else None

    return {
        "path": str(p),
        "type": media_type,
        "duration": duration,
        "width": int(video["width"]) if video and video.get("width") else None,
        "height": int(video["height"]) if video and video.get("height") else None,
        "has_audio": bool(audio),
        "codec": (video or audio or {}).get("codec_name"),
        "format": fmt.get("format_name"),
        "size": int(fmt["size"]) if fmt.get("size") else None,
        "raw": raw,
    }
