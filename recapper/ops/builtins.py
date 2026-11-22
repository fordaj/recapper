"""Built-in operation definitions and registration."""

from __future__ import annotations

from typing import Any

from .title_slide import TitleSlideOperation
from .image_to_video import ImageToVideoOperation
from .side_by_side import ImagesToSideBySideVideoOperation
from .normalize import NormalizeVideoOperation
from .audio_mix import AudioTrackOperation

BUILTIN_OPERATIONS = [
    TitleSlideOperation(),
    ImageToVideoOperation(),
    ImagesToSideBySideVideoOperation(),
    NormalizeVideoOperation(),
    AudioTrackOperation(),
]

# UI clip type -> operation name
CLIP_TYPE_OPERATION_MAP = {
    "title": "title-slide",
    "image": "image-to-video",
    "composition": "images-to-side-by-side-video",
    "video": "normalize-video",
    "audio": "audio-track",
}


def register_builtin_operations(registry: Any) -> None:
    for op in BUILTIN_OPERATIONS:
        clip_types = [ct for ct, name in CLIP_TYPE_OPERATION_MAP.items() if name == op.name]
        if not registry.has(op.name):
            registry.register(op, clip_types=clip_types)
        else:
            # Replace stub with real implementation if present
            registry.unregister(op.name)
            registry.register(op, clip_types=clip_types)
