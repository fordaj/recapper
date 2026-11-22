"""Project/timeline model for Recapper.

This module defines the canonical JSON-serializable project structure used by
the UI, API, and render pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any
import uuid

SCHEMA_VERSION = "1.0"

# Canonical mapping from timeline/UI clip types to operation names.
CLIP_TYPE_OPERATIONS: dict[str, str] = {
    "title": "title-slide",
    "image": "image-to-video",
    "composition": "images-to-side-by-side-video",
    "video": "normalize-video",
    "audio": "audio-track",  # mixed during audio render pass
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str = "id") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass
class RenderSettings:
    width: int = 1920
    height: int = 1080
    fps: int = 30
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    audio_sample_rate: int = 48000
    audio_channels: int = 2
    pixel_format: str = "yuv420p"
    crf: int = 18
    preset: str = "medium"
    output_format: str = "mp4"
    output_name: str = "recap.mp4"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "RenderSettings":
        data = data or {}
        obj = cls()
        for k, v in data.items():
            if hasattr(obj, k):
                setattr(obj, k, v)
        obj.validate()
        return obj

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Render dimensions must be positive")
        if self.fps <= 0:
            raise ValueError("fps must be positive")
        if self.crf < 0 or self.crf > 51:
            raise ValueError("crf must be between 0 and 51")


@dataclass
class MediaAsset:
    id: str
    type: str  # image, video, audio
    name: str
    path: str  # relative to project dir or absolute
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    has_audio: bool | None = None
    codec: str | None = None
    thumbnail: str | None = None
    probe: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MediaAsset":
        return cls(
            id=str(data.get("id") or new_id("m")),
            type=str(data.get("type", "image")),
            name=str(data.get("name", "Untitled")),
            path=str(data.get("path") or data.get("src") or ""),
            duration=_opt_float(data.get("duration")),
            width=_opt_int(data.get("width")),
            height=_opt_int(data.get("height")),
            has_audio=data.get("has_audio") if isinstance(data.get("has_audio"), bool) else None,
            codec=data.get("codec"),
            thumbnail=data.get("thumbnail"),
            probe=dict(data.get("probe") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "path": self.path,
            "duration": self.duration,
            "width": self.width,
            "height": self.height,
            "has_audio": self.has_audio,
            "codec": self.codec,
            "thumbnail": self.thumbnail,
            "probe": self.probe,
        }

    def validate(self) -> None:
        if self.type not in {"image", "video", "audio"}:
            raise ValueError(f"Invalid media type: {self.type}")
        if not self.path:
            raise ValueError(f"Media asset {self.id} missing path")


@dataclass
class Track:
    id: str
    kind: str  # visual, audio
    label: str
    order: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any], order: int = 0) -> "Track":
        return cls(
            id=str(data.get("id") or new_id("t")),
            kind=str(data.get("kind", "visual")),
            label=str(data.get("label") or data.get("name") or data.get("id") or "Track"),
            order=int(data.get("order", order)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "label": self.label, "order": self.order}

    def validate(self) -> None:
        if self.kind not in {"visual", "audio"}:
            raise ValueError(f"Invalid track kind: {self.kind}")


@dataclass
class Clip:
    id: str
    track_id: str
    type: str  # title, image, video, composition, audio
    name: str = "Clip"
    start: float = 0.0
    duration: float = 3.0
    media_id: str | None = None
    params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Clip":
        # Support both canonical and legacy UI field names.
        params = dict(data.get("params") or {})
        # Promote known legacy fields into params for renderability.
        for k in ("title", "subtitle", "color", "compLeft", "compRight", "volume"):
            if k in data and k not in params:
                params[k] = data[k]
        return cls(
            id=str(data.get("id") or new_id("c")),
            track_id=str(data.get("track_id") or data.get("trackId") or ""),
            type=str(data.get("type", "image")),
            name=str(data.get("name", "Clip")),
            start=float(data.get("start", 0) or 0),
            duration=float(data.get("duration", 3) or 3),
            media_id=data.get("media_id") or data.get("mediaId"),
            params=params,
        )

    def to_dict(self) -> dict[str, Any]:
        # Include legacy aliases for current UI compatibility during migration.
        data: dict[str, Any] = {
            "id": self.id,
            "trackId": self.track_id,
            "type": self.type,
            "name": self.name,
            "start": self.start,
            "duration": self.duration,
            "mediaId": self.media_id,
            "params": self.params,
        }
        for k in ("title", "subtitle", "color", "compLeft", "compRight", "volume"):
            if k in self.params:
                data[k] = self.params[k]
        return data

    def validate(self, valid_track_ids: set[str] | None = None) -> None:
        if self.start < 0:
            raise ValueError(f"Clip {self.id} start must be >= 0")
        if self.duration <= 0:
            raise ValueError(f"Clip {self.id} duration must be > 0")
        if valid_track_ids is not None and self.track_id not in valid_track_ids:
            raise ValueError(f"Clip {self.id} references unknown track {self.track_id}")
        if self.type not in CLIP_TYPE_OPERATIONS:
            raise ValueError(f"Clip {self.id} has unsupported type {self.type}")


@dataclass
class Project:
    version: str = SCHEMA_VERSION
    id: str = field(default_factory=lambda: new_id("proj"))
    name: str = "Untitled Recap"
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    media: list[MediaAsset] = field(default_factory=list)
    tracks: list[Track] = field(default_factory=list)
    clips: list[Clip] = field(default_factory=list)
    render: RenderSettings = field(default_factory=RenderSettings)
    meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def default(cls, name: str = "Untitled Recap") -> "Project":
        return cls(
            name=name,
            tracks=[
                Track(id="V1", kind="visual", label="Video 1", order=0),
                Track(id="A1", kind="audio", label="Audio 1", order=1),
            ],
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Project":
        tracks_raw = data.get("tracks") or []
        tracks = [Track.from_dict(t, i) for i, t in enumerate(tracks_raw)]
        if not tracks:
            tracks = cls.default().tracks
        return cls(
            version=str(data.get("version") or SCHEMA_VERSION),
            id=str(data.get("id") or new_id("proj")),
            name=str(data.get("name") or data.get("title") or "Untitled Recap"),
            created_at=str(data.get("created_at") or data.get("createdAt") or _now_iso()),
            updated_at=str(data.get("updated_at") or data.get("updatedAt") or _now_iso()),
            media=[MediaAsset.from_dict(m) for m in (data.get("media") or [])],
            tracks=tracks,
            clips=[Clip.from_dict(c) for c in (data.get("clips") or [])],
            render=RenderSettings.from_dict(data.get("render")),
            meta=dict(data.get("meta") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "media": [m.to_dict() for m in self.media],
            "tracks": [t.to_dict() for t in self.tracks],
            "clips": [c.to_dict() for c in self.clips],
            "render": self.render.to_dict(),
            "meta": self.meta,
        }

    def validate(self, strict_media: bool = True) -> None:
        self.render.validate()
        track_ids: set[str] = set()
        for t in self.tracks:
            t.validate()
            if t.id in track_ids:
                raise ValueError(f"Duplicate track id: {t.id}")
            track_ids.add(t.id)
        media_ids: set[str] = set()
        for m in self.media:
            m.validate()
            if m.id in media_ids:
                raise ValueError(f"Duplicate media id: {m.id}")
            media_ids.add(m.id)
        for c in self.clips:
            c.validate(valid_track_ids=track_ids)
            if strict_media:
                if c.media_id and c.media_id not in media_ids:
                    raise ValueError(f"Clip {c.id} references unknown media {c.media_id}")
                for ref in ("compLeft", "compRight"):
                    mid = c.params.get(ref)
                    if mid and mid not in media_ids:
                        raise ValueError(f"Clip {c.id} references unknown media {mid}")

    def touch(self) -> None:
        self.updated_at = _now_iso()


def _opt_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _opt_int(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
