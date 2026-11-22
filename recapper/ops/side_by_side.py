"""Side-by-side image video operation (ported from gen1)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from recapper.ffmpeg import run_ffmpeg, which
from .base import Operation, OperationCapability, OperationField, OperationResult, RenderContext


def _resolve_input_path(value: str, context: RenderContext) -> Path:
    if value in context.assets:
        a = context.assets[value]
        p = a.get("resolved_path") or a.get("path")
        return Path(p).expanduser().resolve()
    p = Path(value).expanduser()
    if not p.is_absolute():
        p = (context.project_dir / p).resolve()
    return p


class ImagesToSideBySideVideoOperation(Operation):
    name = "images-to-side-by-side-video"
    description = "Compose two images into a side-by-side video segment."
    capability = OperationCapability.COMPOSES
    input_schema = [
        OperationField("left_image", "asset", required=True, ui_label="Left"),
        OperationField("right_image", "asset", required=True, ui_label="Right"),
    ]
    params_schema = [
        OperationField("duration", "number", required=True, default=5, min=0.5, ui_label="Duration (s)"),
        OperationField("width", "integer", required=False, default=1920, min=16),
        OperationField("height", "integer", required=False, default=1080, min=16),
        OperationField("fps", "integer", required=False, default=30, min=1, max=120),
        OperationField("output", "string", required=False, default=""),
    ]
    default_params = {f.name: f.default for f in params_schema if f.default is not None}

    def build(self, inputs: dict[str, Any], params: dict[str, Any], context: RenderContext) -> OperationResult:
        p = self.validate(inputs, params)
        ffmpeg = which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("ffmpeg not found on PATH")

        left = _resolve_input_path(str(inputs["left_image"]), context)
        right = _resolve_input_path(str(inputs["right_image"]), context)
        for src, label in ((left, "Left"), (right, "Right")):
            if not src.exists():
                raise FileNotFoundError(f"{label} image not found: {src}")

        duration = float(p.get("duration", 5))
        width = int(p.get("width", context.render_settings.get("width", 1920)))
        height = int(p.get("height", context.render_settings.get("height", 1080)))
        fps = int(p.get("fps", context.render_settings.get("fps", 30)))
        half_w = width // 2

        filter_complex = (
            f"[0:v]scale=w={half_w}:h={height}:force_original_aspect_ratio=increase,"
            f"crop={half_w}:{height},setsar=1[left];"
            f"[1:v]scale=w={width-half_w}:h={height}:force_original_aspect_ratio=increase,"
            f"crop={width-half_w}:{height},setsar=1[right];"
            f"[left][right]hstack=inputs=2,format=yuv420p[out]"
        )

        output = p.get("output")
        if output:
            out_path = Path(output)
            if not out_path.is_absolute():
                out_path = (context.output_dir / out_path).resolve()
        else:
            out_path = (context.temp_dir / f"side-by-side-{int(duration*1000)}.mp4").resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            ffmpeg, "-y",
            "-loop", "1", "-framerate", str(fps), "-t", str(duration), "-i", str(left),
            "-loop", "1", "-framerate", str(fps), "-t", str(duration), "-i", str(right),
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-map", "2:a:0",
            "-c:v", "libx264",
            "-r", str(fps),
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            str(out_path),
        ]
        run_ffmpeg(cmd)
        return OperationResult(outputs=[out_path], commands=[cmd], artifacts={"output": str(out_path)})
