"""Title slide operation (ported from gen1 title.py)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from recapper.ffmpeg import escape_drawtext, resolve_font, run_ffmpeg, which
from .base import Operation, OperationCapability, OperationField, OperationResult, RenderContext


class TitleSlideOperation(Operation):
    name = "title-slide"
    description = "Generate a title slide video segment with title/subtitle text."
    capability = OperationCapability.GENERATES_VISUAL
    input_schema = []
    params_schema = [
        OperationField("title", "string", required=True, default="Title", ui_label="Title"),
        OperationField("subtitle", "string", required=False, default="", ui_label="Subtitle"),
        OperationField("duration", "number", required=True, default=5, min=0.5, ui_label="Duration (s)"),
        OperationField("color", "color", required=False, default="black", ui_label="Background"),
        OperationField("width", "integer", required=False, default=1920, min=16),
        OperationField("height", "integer", required=False, default=1080, min=16),
        OperationField("fps", "integer", required=False, default=30, min=1, max=120),
        OperationField("font", "string", required=False, default="", description="Font path; auto-resolved if empty"),
        OperationField("output", "string", required=False, default="", description="Output path; defaults to temp dir"),
    ]
    default_params = {f.name: f.default for f in params_schema if f.default is not None}

    def build(self, inputs: dict[str, Any], params: dict[str, Any], context: RenderContext) -> OperationResult:
        p = self.validate(inputs, params)
        ffmpeg = which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("ffmpeg not found on PATH")

        title = escape_drawtext(p.get("title", ""))
        subtitle = escape_drawtext(p.get("subtitle", ""))
        duration = float(p.get("duration", 5))
        color = str(p.get("color", "black"))
        width = int(p.get("width", context.render_settings.get("width", 1920)))
        height = int(p.get("height", context.render_settings.get("height", 1080)))
        fps = int(p.get("fps", context.render_settings.get("fps", 30)))

        font = resolve_font(p.get("font") or None)
        font_opt = f":fontfile='{escape_drawtext(font)}'" if font else ""

        # Build drawtext filter; include subtitle only if present.
        vf_parts = [
            f"drawtext=text='{title}'{font_opt}:x=(w-text_w)/2:y=(h/2-50):fontsize=72:fontcolor=white"
        ]
        if subtitle:
            vf_parts.append(
                f"drawtext=text='{subtitle}'{font_opt}:x=(w-text_w)/2:y=(h/2+50):fontsize=48:fontcolor=white"
            )
        fade_out_start = max(0, duration - 1)
        vf_parts.append(f"fade=t=in:st=0:d=1")
        vf_parts.append(f"fade=t=out:st={fade_out_start}:d=1")
        vf = ",".join(vf_parts)

        output = p.get("output")
        if output:
            out_path = Path(output)
            if not out_path.is_absolute():
                out_path = (context.output_dir / out_path).resolve()
        else:
            out_path = (context.temp_dir / f"title-{abs(hash((title, subtitle, duration))) % 100000}.mp4").resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            ffmpeg, "-y",
            "-f", "lavfi", "-i", f"color=c={color}:s={width}x{height}:d={duration}:r={fps}",
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-vf", vf,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-r", str(fps),
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            str(out_path),
        ]
        run_ffmpeg(cmd)
        return OperationResult(outputs=[out_path], commands=[cmd], artifacts={"output": str(out_path)})
