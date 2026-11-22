"""Normalize and concatenate operations (ported from gen1 concatenate.py)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Sequence

from recapper.ffmpeg import has_audio_stream, run_ffmpeg, which
from .base import Operation, OperationCapability, OperationField, OperationResult, RenderContext


DEFAULT_RENDER = {
    "width": 1920,
    "height": 1080,
    "fps": 30,
    "video_codec": "libx264",
    "audio_codec": "aac",
    "audio_bitrate": "128k",
    "audio_sample_rate": 48000,
    "audio_channels": 2,
    "pixel_format": "yuv420p",
}


def _render(settings: dict[str, Any] | None) -> dict[str, Any]:
    r = dict(DEFAULT_RENDER)
    if settings:
        r.update(settings)
    return r


def normalize_video(input_path: str | Path, output_path: str | Path, settings: dict[str, Any] | None = None) -> Path:
    """Normalize a single video to a common render profile."""
    ffmpeg = which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found on PATH")
    src = Path(input_path).expanduser().resolve()
    out = Path(output_path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    r = _render(settings)
    w, h, fps = int(r["width"]), int(r["height"]), int(r["fps"])
    has_audio = has_audio_stream(src)

    vf = (
        f"scale=w={w}:h={h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,format={r['pixel_format']}"
    )

    if has_audio:
        cmd = [
            ffmpeg, "-y", "-i", str(src),
            "-vf", vf,
            "-c:v", str(r["video_codec"]),
            "-pix_fmt", str(r["pixel_format"]),
            "-profile:v", "high", "-level", "4.0",
            "-r", str(fps),
            "-fps_mode", "cfr",
            "-fflags", "+genpts",
            "-c:a", str(r["audio_codec"]),
            "-b:a", str(r["audio_bitrate"]),
            "-ar", str(r["audio_sample_rate"]),
            "-ac", str(r["audio_channels"]),
            str(out),
        ]
    else:
        cmd = [
            ffmpeg, "-y", "-i", str(src),
            "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate={r['audio_sample_rate']}",
            "-vf", vf,
            "-c:v", str(r["video_codec"]),
            "-pix_fmt", str(r["pixel_format"]),
            "-profile:v", "high", "-level", "4.0",
            "-r", str(fps),
            "-fps_mode", "cfr",
            "-fflags", "+genpts",
            "-c:a", str(r["audio_codec"]),
            "-b:a", str(r["audio_bitrate"]),
            "-ar", str(r["audio_sample_rate"]),
            "-ac", str(r["audio_channels"]),
            "-map", "0:v:0", "-map", "1:a:0",
            "-shortest",
            str(out),
        ]
    run_ffmpeg(cmd)
    return out


def normalize_many(inputs: Sequence[str | Path], out_dir: str | Path, settings: dict[str, Any] | None = None, workers: int = 4) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    def _one(p: str | Path) -> Path:
        src = Path(p)
        return normalize_video(src, out_dir / src.name, settings=settings)

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        return list(ex.map(_one, inputs))


def write_concat_list(files: Sequence[Path], list_path: str | Path) -> Path:
    lp = Path(list_path)
    lp.parent.mkdir(parents=True, exist_ok=True)
    with lp.open("w", encoding="utf-8") as f:
        for p in files:
            f.write(f"file '{Path(p).resolve().as_posix()}'\n")
    return lp


def concat_videos(inputs: Sequence[str | Path], output_path: str | Path, settings: dict[str, Any] | None = None) -> Path:
    ffmpeg = which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found on PATH")
    if not inputs:
        raise ValueError("No inputs to concatenate")
    out = Path(output_path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    list_path = out.parent / f".{out.stem}.concat.txt"
    write_concat_list([Path(p) for p in inputs], list_path)
    r = _render(settings)
    cmd = [
        ffmpeg, "-y",
        "-f", "concat", "-safe", "0", "-i", str(list_path),
        "-c:v", str(r["video_codec"]),
        "-c:a", str(r["audio_codec"]),
        "-b:a", str(r["audio_bitrate"]),
        "-ar", str(r["audio_sample_rate"]),
        "-ac", str(r["audio_channels"]),
        "-pix_fmt", str(r["pixel_format"]),
        str(out),
    ]
    try:
        run_ffmpeg(cmd)
    finally:
        try:
            list_path.unlink()
        except Exception:
            pass
    return out


class NormalizeVideoOperation(Operation):
    name = "normalize-video"
    description = "Normalize a video segment to the project render profile."
    capability = OperationCapability.TRANSFORMS_VISUAL
    input_schema = [
        OperationField("video", "asset", required=True, description="Media asset ID or path"),
    ]
    params_schema = [
        OperationField("duration", "number", required=False, default=None, min=0.1),
        OperationField("width", "integer", required=False, default=1920, min=16),
        OperationField("height", "integer", required=False, default=1080, min=16),
        OperationField("fps", "integer", required=False, default=30, min=1, max=120),
        OperationField("output", "string", required=False, default=""),
    ]
    default_params = {f.name: f.default for f in params_schema if f.default is not None}

    def build(self, inputs: dict[str, Any], params: dict[str, Any], context: RenderContext) -> OperationResult:
        p = self.validate(inputs, params)
        value = str(inputs["video"])
        if value in context.assets:
            a = context.assets[value]
            src = Path(a.get("resolved_path") or a.get("path")).expanduser().resolve()
        else:
            src = Path(value).expanduser()
            if not src.is_absolute():
                src = (context.project_dir / src).resolve()
        if not src.exists():
            raise FileNotFoundError(f"Video not found: {src}")

        output = p.get("output")
        if output:
            out_path = Path(output)
            if not out_path.is_absolute():
                out_path = (context.output_dir / out_path).resolve()
        else:
            out_path = (context.temp_dir / f"norm-{src.stem}.mp4").resolve()

        settings = dict(context.render_settings)
        settings.update({k: p[k] for k in ("width", "height", "fps") if p.get(k) is not None})
        out = normalize_video(src, out_path, settings=settings)

        # Optional trim/limit duration post-normalize? Better to do in ffmpeg; for now, if duration specified, trim.
        dur = p.get("duration")
        if dur is not None:
            trimmed = out.with_name(out.stem + ".trim.mp4")
            ffmpeg = which("ffmpeg")
            cmd = [ffmpeg, "-y", "-i", str(out), "-t", str(float(dur)), "-c", "copy", str(trimmed)]
            run_ffmpeg(cmd)
            out = trimmed

        return OperationResult(outputs=[out], commands=[], artifacts={"output": str(out)})
