"""Built-in operation definitions.

These define the canonical operation names and schemas. The ffmpeg builders are
implemented in Task 3; until then, build() raises NotImplementedError.
"""

from __future__ import annotations

from typing import Any

from .base import Operation, OperationCapability, OperationField, RenderContext, OperationResult


class TitleSlideOperation(Operation):
    name = "title-slide"
    description = "Generate a title slide video segment."
    capability = OperationCapability.GENERATES_VISUAL
    input_schema = []
    params_schema = [
        OperationField("title", "string", required=True, default="Title", ui_label="Title"),
        OperationField("subtitle", "string", required=False, default="", ui_label="Subtitle"),
        OperationField("duration", "number", required=True, default=5, min=0.5, ui_label="Duration (s)"),
        OperationField("color", "color", required=False, default="#000000", ui_label="Background"),
        OperationField("width", "integer", required=False, default=1920, min=16),
        OperationField("height", "integer", required=False, default=1080, min=16),
        OperationField("fps", "integer", required=False, default=30, min=1, max=120),
        OperationField("font", "string", required=False, default="", description="Font path or family; resolved at render time"),
    ]
    default_params = {f.name: f.default for f in params_schema if f.default is not None}


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
    ]
    default_params = {f.name: f.default for f in params_schema if f.default is not None}


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
    ]
    default_params = {f.name: f.default for f in params_schema if f.default is not None}


class NormalizeVideoOperation(Operation):
    name = "normalize-video"
    description = "Normalize a video segment to the project render profile."
    capability = OperationCapability.TRANSFORMS_VISUAL
    input_schema = [
        OperationField("video", "asset", required=True, description="Media asset ID or path"),
    ]
    params_schema = [
        OperationField("duration", "number", required=False, default=None, min=0.1, description="Trim/limit duration; null uses source"),
        OperationField("width", "integer", required=False, default=1920, min=16),
        OperationField("height", "integer", required=False, default=1080, min=16),
        OperationField("fps", "integer", required=False, default=30, min=1, max=120),
    ]
    default_params = {f.name: f.default for f in params_schema if f.name != "duration" or f.default is not None}


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
    ]
    default_params = {f.name: f.default for f in params_schema if f.default is not None}


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
