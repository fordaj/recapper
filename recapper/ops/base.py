"""Base contract for extensible ffmpeg operations.

Adding a new operation should require only:
1. Subclassing Operation (or providing an object with the same interface).
2. Declaring name, schema/defaults/capability.
3. Implementing build() to produce ffmpeg command(s) or a render artifact.
4. Registering it with the registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class OperationCapability(str, Enum):
    """What kind of timeline/render role an operation plays."""

    GENERATES_VISUAL = "generates_visual"
    GENERATES_AUDIO = "generates_audio"
    TRANSFORMS_VISUAL = "transforms_visual"
    TRANSFORMS_AUDIO = "transforms_audio"
    COMPOSES = "composes"
    MIXES_AUDIO = "mixes_audio"


@dataclass
class OperationField:
    """Declarative parameter/input field used for validation and UI metadata."""

    name: str
    type: str  # string, number, integer, boolean, color, path, asset, enum
    required: bool = False
    default: Any = None
    description: str = ""
    choices: list[Any] | None = None
    min: float | None = None
    max: float | None = None
    ui_label: str | None = None
    ui_group: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "name": self.name,
            "type": self.type,
            "required": self.required,
            "description": self.description,
        }
        if self.default is not None:
            data["default"] = self.default
        if self.choices is not None:
            data["choices"] = list(self.choices)
        if self.min is not None:
            data["min"] = self.min
        if self.max is not None:
            data["max"] = self.max
        if self.ui_label is not None:
            data["ui_label"] = self.ui_label
        if self.ui_group is not None:
            data["ui_group"] = self.ui_group
        return data


@dataclass
class OperationResult:
    """Result of building/running an operation."""

    outputs: list[Path] = field(default_factory=list)
    commands: list[list[str]] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)
    logs: list[str] = field(default_factory=list)


@dataclass
class RenderContext:
    """Runtime context passed to operation builders."""

    project_dir: Path
    temp_dir: Path
    output_dir: Path
    render_settings: dict[str, Any] = field(default_factory=dict)
    assets: dict[str, Any] = field(default_factory=dict)  # asset_id -> resolved asset


class Operation:
    """Base operation. Subclasses must set metadata and implement build()."""

    name: str = ""
    description: str = ""
    capability: OperationCapability = OperationCapability.GENERATES_VISUAL
    input_schema: list[OperationField] = []
    params_schema: list[OperationField] = []
    default_params: dict[str, Any] = {}

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "capability": self.capability.value,
            "inputs": [f.to_dict() for f in self.input_schema],
            "params": [f.to_dict() for f in self.params_schema],
            "defaults": dict(self.default_params),
        }

    def validate(self, inputs: dict[str, Any], params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Validate and normalize inputs/params, returning normalized params."""
        errors: list[str] = []
        normalized_params = dict(self.default_params)
        normalized_params.update(params or {})

        for spec in self.input_schema:
            if spec.required and spec.name not in inputs:
                errors.append(f"Missing required input: {spec.name}")
            if spec.name in inputs:
                self._validate_field(spec, inputs[spec.name], errors, prefix="input")

        known_params = {f.name for f in self.params_schema}
        for spec in self.params_schema:
            if spec.required and spec.name not in normalized_params:
                errors.append(f"Missing required param: {spec.name}")
            if spec.name in normalized_params:
                normalized_params[spec.name] = self._validate_field(
                    spec, normalized_params[spec.name], errors, prefix="param"
                )
        # Keep unknown params? Be permissive but deterministic; ignore unknown.
        normalized_params = {k: v for k, v in normalized_params.items() if k in known_params or not known_params}

        if errors:
            raise ValueError(f"Operation '{self.name}' validation failed: {'; '.join(errors)}")
        return normalized_params

    def _validate_field(self, spec: OperationField, value: Any, errors: list[str], prefix: str) -> Any:
        if value is None:
            if spec.required:
                errors.append(f"Missing required {prefix}: {spec.name}")
            return value
        t = spec.type
        try:
            if t in ("number",):
                value = float(value)
            elif t in ("integer",):
                value = int(value)
            elif t in ("boolean",):
                if not isinstance(value, bool):
                    errors.append(f"{prefix} {spec.name} must be boolean")
            elif t in ("string", "color", "path", "asset", "enum"):
                value = str(value)
        except (TypeError, ValueError):
            errors.append(f"{prefix} {spec.name} must be {t}")
            return value

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if spec.min is not None and value < spec.min:
                errors.append(f"{prefix} {spec.name} must be >= {spec.min}")
            if spec.max is not None and value > spec.max:
                errors.append(f"{prefix} {spec.name} must be <= {spec.max}")
        if spec.choices is not None and value not in spec.choices:
            errors.append(f"{prefix} {spec.name} must be one of {spec.choices}")
        return value

    def build(self, inputs: dict[str, Any], params: dict[str, Any], context: RenderContext) -> OperationResult:
        """Build ffmpeg command(s)/artifacts. Implemented by concrete operations."""
        raise NotImplementedError(f"Operation '{self.name}' does not implement build()")
