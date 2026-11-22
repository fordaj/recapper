"""Audio overlay/mix operations (ported from gen1 overlay_audio)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from recapper.ffmpeg import run_ffmpeg, which
from .base import Operation, OperationCapability, OperationField, OperationResult, RenderContext


def overlay_audio(
    video_path: str | Path,
    audio_path: str | Path,
    output_path: str | Path,
    *,
    video_volume: float = 1.0,
    audio_volume: float = 1.0,
    duration_policy: str = "shortest",  # shortest | video | audio
    audio_bitrate: str = "192k",
) -> Path:
    """Overlay/mix an audio file onto a video file."""
    ffmpeg = which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found on PATH")
    video = Path(video_path).expanduser().resolve()
    audio = Path(audio_path).expanduser().resolve()
    out = Path(output_path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    filter_complex = (
        f"[0:a]volume={video_volume}[a0];"
        f"[1:a]volume={audio_volume}[a1];"
        f"[a0][a1]amix=inputs=2:dropout_transition=0:normalize=0[a]"
    )
    cmd = [
        ffmpeg, "-y",
        "-i", str(video),
        "-i", str(audio),
        "-filter_complex", filter_complex,
        "-map", "0:v:0",
        "-map", "[a]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", str(audio_bitrate),
    ]
    if duration_policy == "shortest":
        cmd += ["-shortest"]
    elif duration_policy == "video":
        cmd += ["-t", str(_probe_duration(video))]
    elif duration_policy == "audio":
        cmd += ["-t", str(_probe_duration(audio))]
    cmd += [str(out)]
    run_ffmpeg(cmd)
    return out


def mix_audio_to_video(
    video_path: str | Path,
    audio_inputs: Sequence[dict[str, Any]],
    output_path: str | Path,
    *,
    duration_policy: str = "video",
    audio_bitrate: str = "192k",
) -> Path:
    """Mix multiple audio inputs onto a video. Each input: {path, volume, start, fade_in, fade_out}."""
    ffmpeg = which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found on PATH")
    video = Path(video_path).expanduser().resolve()
    out = Path(output_path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if not audio_inputs:
        # Just ensure audio exists? copy
        shutil.copy2(video, out)
        return out

    cmd = [ffmpeg, "-y", "-i", str(video)]
    for a in audio_inputs:
        cmd += ["-i", str(Path(a["path"]).expanduser().resolve())]

    filters = []
    mix_labels = []
    # include original video audio if present? we'll try to include as [0:a] optionally; simpler: mix only provided inputs and also original audio if exists
    # We'll always attempt to include video audio; if missing, ffmpeg will fail - so check.
    has_video_audio = _has_audio(video)
    if has_video_audio:
        filters.append("[0:a]volume=1.0[base]")
        mix_labels.append("[base]")

    for i, a in enumerate(audio_inputs, start=1):
        vol = float(a.get("volume", 1.0))
        start = float(a.get("start", 0) or 0)
        delay_ms = int(start * 1000)
        label = f"a{i}"
        chain = f"[{i}:a]adelay={delay_ms}|{delay_ms},volume={vol}"
        fade_in = float(a.get("fade_in", 0) or 0)
        fade_out = float(a.get("fade_out", 0) or 0)
        dur = a.get("duration")
        if fade_in > 0:
            chain += f",afade=t=in:st={start}:d={fade_in}"
        if fade_out > 0 and dur:
            st = max(0, start + float(dur) - fade_out)
            chain += f",afade=t=out:st={st}:d={fade_out}"
        chain += f"[{label}]"
        filters.append(chain)
        mix_labels.append(f"[{label}]")

    if not mix_labels:
        # no audio at all
        cmd = [ffmpeg, "-y", "-i", str(video), "-c", "copy", str(out)]
        run_ffmpeg(cmd)
        return out

    filters.append(f"{''.join(mix_labels)}amix=inputs={len(mix_labels)}:dropout_transition=0:normalize=0[mix]")
    cmd += [
        "-filter_complex", ";".join(filters),
        "-map", "0:v:0", "-map", "[mix]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", str(audio_bitrate),
    ]
    if duration_policy == "shortest":
        cmd += ["-shortest"]
    elif duration_policy == "video":
        cmd += ["-t", str(_probe_duration(video))]
    cmd += [str(out)]
    run_ffmpeg(cmd)
    return out


class AudioTrackOperation(Operation):
    name = "audio-track"
    description = "Place/mix an audio asset on the timeline audio pass."
    capability = OperationCapability.MIXES_AUDIO
    input_schema = [
        OperationField("audio", "asset", required=True, description="Audio media asset ID or path"),
    ]
    params_schema = [
        OperationField("start", "number", required=False, default=0, min=0),
        OperationField("duration", "number", required=False, default=None, min=0.1),
        OperationField("volume", "number", required=False, default=1.0, min=0, max=2.0, ui_label="Volume"),
        OperationField("fade_in", "number", required=False, default=0, min=0),
        OperationField("fade_out", "number", required=False, default=0, min=0),
        OperationField("output", "string", required=False, default=""),
    ]
    default_params = {f.name: f.default for f in params_schema if f.default is not None}

    def build(self, inputs: dict[str, Any], params: dict[str, Any], context: RenderContext) -> OperationResult:
        # Audio track is compiled by the render pipeline; build returns metadata.
        p = self.validate(inputs, params)
        value = str(inputs["audio"])
        if value in context.assets:
            a = context.assets[value]
            src = str(Path(a.get("resolved_path") or a.get("path")).expanduser().resolve())
        else:
            src = str(Path(value).expanduser())
        return OperationResult(outputs=[], commands=[], artifacts={"audio": {"path": src, **p}})


def _probe_duration(path: Path) -> float:
    from recapper.ffmpeg import probe_media
    try:
        d = probe_media(path).get("duration")
        return float(d) if d else 0.0
    except Exception:
        return 0.0


def _has_audio(path: Path) -> bool:
    from recapper.ffmpeg import has_audio_stream
    return has_audio_stream(path)
