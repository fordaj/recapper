"""Render/export pipeline.

Compiles a Project timeline into ffmpeg operations and produces a final video.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
import shutil
import tempfile

from .ffmpeg import run_ffmpeg, which
from .model import Project, Clip
from .ops import registry
from .ops.base import RenderContext
from .ops.normalize import normalize_video, concat_videos
from .ops.audio_mix import mix_audio_to_video
from .project import resolve_asset_path


@dataclass
class RenderPlanItem:
    index: int
    clip_id: str | None
    type: str
    start: float
    duration: float
    operation: str
    inputs: dict[str, Any]
    params: dict[str, Any]


@dataclass
class RenderResult:
    output_path: Path
    plan: list[RenderPlanItem] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)


class RenderPipeline:
    def __init__(self, project: Project, project_path: str | Path | None = None):
        self.project = project
        self.project_path = Path(project_path).expanduser().resolve() if project_path else None
        self.project_dir = self.project_path.parent if self.project_path else Path.cwd()
        self.logs: list[str] = []
        self.progress_cb: Callable[[float, str, str], None] | None = None

    def log(self, msg: str) -> None:
        self.logs.append(msg)
        if self.progress_cb:
            # don't change progress here
            pass

    def progress(self, pct: float, stage: str, message: str = "") -> None:
        self.log(f"[{pct:.0f}%] {stage}: {message}" if message else f"[{pct:.0f}%] {stage}")
        if self.progress_cb:
            self.progress_cb(pct, stage, message)

    def _asset_map(self) -> dict[str, dict[str, Any]]:
        out = {}
        for m in self.project.media:
            resolved = None
            try:
                if self.project_path:
                    resolved = str(resolve_asset_path(self.project_path, m.path))
                else:
                    p = Path(m.path).expanduser()
                    resolved = str((self.project_dir / p).resolve() if not p.is_absolute() else p.resolve())
            except Exception:
                resolved = m.path
            out[m.id] = {**m.to_dict(), "resolved_path": resolved}
        return out

    def compile_visual_plan(self) -> list[RenderPlanItem]:
        settings = self.project.render.to_dict()
        assets = self._asset_map()
        visual_tracks = [t for t in sorted(self.project.tracks, key=lambda t: t.order) if t.kind == "visual"]
        # For now, render primary visual track (first). Future: compositing.
        track = visual_tracks[0] if visual_tracks else None
        clips = [c for c in self.project.clips if track and c.track_id == track.id]
        clips.sort(key=lambda c: (c.start, c.id))

        plan: list[RenderPlanItem] = []
        t = 0.0
        idx = 0
        for clip in clips:
            start = max(0.0, float(clip.start))
            dur = max(0.1, float(clip.duration))
            if start > t + 0.001:
                gap_dur = start - t
                plan.append(RenderPlanItem(
                    index=idx, clip_id=None, type="gap", start=t, duration=gap_dur,
                    operation="gap-black", inputs={}, params={"duration": gap_dur, **{k: settings.get(k) for k in ("width","height","fps")}}
                ))
                idx += 1
                t = start
            elif start < t - 0.001:
                # overlap: trim clip to start at t
                overlap = t - start
                dur = max(0.1, dur - overlap)
                start = t
            op_name = registry.operation_for_clip_type(clip.type)
            if not op_name:
                self.log(f"Skipping unsupported clip type {clip.type} ({clip.id})")
                t = max(t, start + dur)
                continue
            inputs, params = self._clip_to_operation(clip, assets, settings)
            plan.append(RenderPlanItem(
                index=idx, clip_id=clip.id, type=clip.type, start=start, duration=dur,
                operation=op_name, inputs=inputs, params=params,
            ))
            idx += 1
            t = start + dur
        return plan

    def _clip_to_operation(self, clip: Clip, assets: dict[str, dict[str, Any]], settings: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        p = dict(clip.params)
        base = {"width": settings.get("width", 1920), "height": settings.get("height", 1080), "fps": settings.get("fps", 30), "duration": clip.duration}
        if clip.type == "title":
            params = {**base, "title": p.get("title", clip.name), "subtitle": p.get("subtitle", ""), "color": p.get("color", "black")}
            return {}, params
        if clip.type == "image":
            params = {**base}
            return {"image": clip.media_id or p.get("image")}, params
        if clip.type == "composition":
            params = {**base}
            left = p.get("compLeft") or p.get("left_image")
            right = p.get("compRight") or p.get("right_image")
            return {"left_image": left, "right_image": right}, params
        if clip.type == "video":
            params = {**base}
            return {"video": clip.media_id or p.get("video")}, params
        if clip.type == "audio":
            params = {"start": clip.start, "duration": clip.duration, "volume": float(p.get("volume", 100)) / 100.0 if float(p.get("volume", 1)) > 2 else float(p.get("volume", 1))}
            return {"audio": clip.media_id or p.get("audio")}, params
        return {}, {**base}

    def render(self, output_path: str | Path | None = None, keep_temp: bool = False) -> RenderResult:
        if not which("ffmpeg") or not which("ffprobe"):
            raise RuntimeError("ffmpeg and ffprobe are required on PATH")

        settings = self.project.render.to_dict()
        out = Path(output_path).expanduser().resolve() if output_path else (self.project_dir / settings.get("output_name", "recap.mp4")).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)

        temp_root = self.project_dir / ".recapper-cache" / "render"
        temp_root.mkdir(parents=True, exist_ok=True)
        temp_dir = Path(tempfile.mkdtemp(prefix="job-", dir=str(temp_root)))
        assets = self._asset_map()
        ctx = RenderContext(project_dir=self.project_dir, temp_dir=temp_dir, output_dir=out.parent, render_settings=settings, assets=assets)

        try:
            self.progress(5, "compile", "Compiling timeline")
            plan = self.compile_visual_plan()
            if not plan:
                raise RuntimeError("Timeline has no renderable visual clips")

            # Visual pass
            visual_segments: list[Path] = []
            total = len(plan)
            for i, item in enumerate(plan):
                pct = 10 + (i / max(1, total)) * 60
                self.progress(pct, "visual", f"Rendering {item.type} {i+1}/{total}")
                seg = self._render_visual_item(item, ctx)
                visual_segments.append(seg)

            # Concat visual
            self.progress(75, "assemble", "Concatenating visual segments")
            visual_out = temp_dir / "visual.mp4"
            concat_videos(visual_segments, visual_out, settings=settings)

            # Audio pass
            self.progress(85, "audio", "Mixing audio")
            final_out = self._render_audio(visual_out, temp_dir, settings)

            self.progress(95, "finalize", "Writing output")
            if final_out.resolve() != out.resolve():
                shutil.copy2(final_out, out)

            self.progress(100, "done", f"Exported {out}")
            return RenderResult(output_path=out, plan=plan, logs=list(self.logs))
        finally:
            if not keep_temp:
                shutil.rmtree(temp_dir, ignore_errors=True)

    def _render_visual_item(self, item: RenderPlanItem, ctx: RenderContext) -> Path:
        settings = ctx.render_settings
        if item.operation == "gap-black":
            out = ctx.temp_dir / f"{item.index:04d}-gap.mp4"
            self._make_black_segment(out, item.duration, settings)
            return out
        op = registry.get(item.operation)
        params = dict(item.params)
        params.setdefault("output", str(ctx.temp_dir / f"{item.index:04d}-{item.type}.mp4"))
        res = op.build(item.inputs, params, ctx)
        if not res.outputs:
            raise RuntimeError(f"Operation {item.operation} produced no output")
        seg = res.outputs[0]
        # Ensure normalized
        norm = ctx.temp_dir / f"{item.index:04d}-{item.type}.norm.mp4"
        normalize_video(seg, norm, settings=settings)
        return norm

    def _make_black_segment(self, out: Path, duration: float, settings: dict[str, Any]) -> Path:
        ffmpeg = which("ffmpeg")
        w = int(settings.get("width", 1920))
        h = int(settings.get("height", 1080))
        fps = int(settings.get("fps", 30))
        sr = int(settings.get("audio_sample_rate", 48000))
        cmd = [
            ffmpeg, "-y",
            "-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:d={duration}:r={fps}",
            "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate={sr}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
            "-c:a", "aac", "-b:a", "128k", "-shortest",
            str(out),
        ]
        run_ffmpeg(cmd)
        return out

    def _render_audio(self, visual_out: Path, temp_dir: Path, settings: dict[str, Any]) -> Path:
        assets = self._asset_map()
        audio_clips = [c for c in self.project.clips if any(t.id == c.track_id and t.kind == "audio" for t in self.project.tracks)]
        if not audio_clips:
            return visual_out
        inputs = []
        for c in sorted(audio_clips, key=lambda x: x.start):
            if not c.media_id:
                continue
            a = assets.get(c.media_id)
            if not a:
                continue
            vol = c.params.get("volume", 100)
            try:
                vol = float(vol)
            except Exception:
                vol = 100.0
            if vol > 2:  # UI stores 0-100
                vol = vol / 100.0
            inputs.append({
                "path": a["resolved_path"],
                "volume": vol,
                "start": float(c.start),
                "duration": float(c.duration),
            })
        if not inputs:
            return visual_out
        out = temp_dir / "final.mp4"
        mix_audio_to_video(visual_out, inputs, out, duration_policy="video", audio_bitrate=str(settings.get("audio_bitrate", "192k")))
        return out
