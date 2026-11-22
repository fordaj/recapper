"""Image-to-video operation (ported from gen1 image_to_video)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from recapper.ffmpeg import run_ffmpeg, which
from .base import Operation, OperationCapability, OperationField, OperationResult, RenderContext


def _resolve_input_path(value: str, context: RenderContext) -> Path:
    # value may be asset id or path
    if value in context.assets:
        a = context.assets[value]
        p = a.get("resolved_path") or a.get("path")
        return Path(p).expanduser().resolve()
    p = Path(value).expanduser()
    if not p.is_absolute():
        p = (context.project_dir / p).resolve()
    return p


class ImageToVideoOperation(Operation):
    name = "image-to-video"
    description = "Convert a still image into a timed video segment."
    capability = OperationCapability.GENERATES_VISUAL
    input_schema = [
        OperationField("image", "asset", required=True, description="Media asset ID or path"),
    ]
    params_schema = [
        OperationField("duration", "number", required=True, default=5, min=0.5, ui_label="Duration (s)"),
        OperationField("width", "integer", required=False, default=1920, min=16),
        OperationField("height", "integer", required=False, default=1080, min=16),
        OperationField("fps", "integer", required=False, default=30, min=1, max=120),
        OperationField("fit", "enum", required=False, default="cover", choices=["cover", "contain", "stretch"]),
        OperationField("output", "string", required=False, default=""),
    ]
    default_params = {f.name: f.default for f in params_schema if f.default is not None}

    def build(self, inputs: dict[str, Any], params: dict[str, Any], context: RenderContext) -> OperationResult:
        p = self.validate(inputs, params)
        ffmpeg = which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("ffmpeg not found on PATH")

        src = _resolve_input_path(str(inputs["image"]), context)
        if not src.exists():
            raise FileNotFoundError(f"Image not found: {src}")

        duration = float(p.get("duration", 5))
        width = int(p.get("width", context.render_settings.get("width", 1920)))
        height = int(p.get("height", context.render_settings.get("height", 1080)))
        fps = int(p.get("fps", context.render_settings.get("fps", 30)))
        fit = p.get("fit", "cover")

        if fit == "cover":
            vf = (
                f"scale=w={width}:h={height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},setsar=1,format=yuv420p"
            )
        elif fit == "contain":
            vf = (
                f"scale=w={width}:h={height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p"
            )
        else:
            vf = f"scale={width}:{height},setsar=1,format=yuv420p"

        output = p.get("output")
        if output:
            out_path = Path(output)
            if not out_path.is_absolute():
                out_path = (context.output_dir / out_path).resolve()
        else:
            out_path = (context.temp_dir / f"image-{src.stem}-{int(duration*1000)}.mp4").resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            ffmpeg, "-y",
            "-loop", "1",
            "-framerate", str(fps),
            "-i", str(src),
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-t", str(duration),
            "-vf", vf,
            "-c:v", "libx264",
            "-r", str(fps),
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            str(out_path),
        ]
        run_ffmpeg(cmd)
        return OperationResult(outputs=[out_path], commands=[cmd], artifacts={"output": str(out_path)})
