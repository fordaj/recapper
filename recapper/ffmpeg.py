"""FFmpeg/ffprobe utilities.

Shared helpers for availability checks, probing, command execution, and temp
workspace management used by operations and the render pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence
import json
import os
import shutil
import subprocess
import tempfile


class FFmpegError(RuntimeError):
    pass


class FFmpegCommandError(FFmpegError):
    def __init__(self, cmd: Sequence[str], returncode: int, stdout: str, stderr: str):
        self.cmd = list(cmd)
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        tail = "\n".join((stderr or stdout).strip().splitlines()[-20:])
        super().__init__(f"ffmpeg command failed ({returncode}): {tail or 'no output'}")


@dataclass
class CommandResult:
    cmd: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


@dataclass
class TempWorkspace:
    path: Path
    keep: bool = False

    def __enter__(self) -> "TempWorkspace":
        self.path.mkdir(parents=True, exist_ok=True)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if not self.keep and self.path.exists():
            shutil.rmtree(self.path, ignore_errors=True)

    def file(self, name: str) -> Path:
        self.path.mkdir(parents=True, exist_ok=True)
        return self.path / name


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


def run_command(cmd: Sequence[str], timeout: int | None = None, cwd: str | Path | None = None) -> CommandResult:
    try:
        proc = subprocess.run(
            list(cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
            cwd=str(cwd) if cwd else None,
        )
    except FileNotFoundError as e:
        raise FFmpegError(f"Command not found: {cmd[0]}") from e
    except subprocess.TimeoutExpired as e:
        raise FFmpegError(f"Command timed out: {' '.join(cmd)}") from e
    return CommandResult(cmd=list(cmd), returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)


def run_ffmpeg(cmd: Sequence[str], timeout: int | None = None, cwd: str | Path | None = None) -> CommandResult:
    r = run_command(cmd, timeout=timeout, cwd=cwd)
    if r.returncode != 0:
        raise FFmpegCommandError(r.cmd, r.returncode, r.stdout, r.stderr)
    return r


def ensure_temp_dir(base: str | Path | None = None, prefix: str = "recapper-") -> Path:
    if base:
        p = Path(base)
        p.mkdir(parents=True, exist_ok=True)
        d = Path(tempfile.mkdtemp(prefix=prefix, dir=str(p)))
    else:
        d = Path(tempfile.mkdtemp(prefix=prefix))
    return d


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
    fmt_name = (fmt.get("format_name") or "").lower()
    if video and not audio and any(x in fmt_name for x in ["image", "jpeg", "png", "webp", "gif", "bmp", "tiff", "mjpeg"]):
        media_type = "image"
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


def has_audio_stream(path: str | Path) -> bool:
    try:
        return bool(probe_media(path).get("has_audio"))
    except Exception:
        return False


def resolve_font(preferred: str | None = None) -> str | None:
    """Resolve a font path for ffmpeg drawtext. Returns a path or None."""
    candidates: list[Path] = []
    if preferred:
        p = Path(preferred).expanduser()
        if p.exists():
            return str(p)
        # Maybe a font name; let ffmpeg/fontconfig handle via font=... not implemented here.
    # Common macOS/Linux locations
    candidates.extend([
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
        Path("/Library/Fonts/Arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
    ])
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def escape_drawtext(text: str) -> str:
    # ffmpeg drawtext escaping: \ : ' and also handle newlines
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace("%", "\\%")
        .replace("\n", "\\n")
    )
