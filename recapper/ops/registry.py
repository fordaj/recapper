"""Operation registry.

This is the extension point for "name + ffmpeg operation". Register an
Operation instance here and the rest of the system can discover it by name.
"""

from __future__ import annotations

from typing import Any

from .base import Operation


class OperationRegistry:
    def __init__(self) -> None:
        self._operations: dict[str, Operation] = {}
        # Map timeline/UI clip types to operation names.
        self._clip_type_operations: dict[str, str] = {}

    def register(self, operation: Operation, *, clip_types: list[str] | None = None) -> Operation:
        if not operation.name:
            raise ValueError("Operation must have a name")
        if operation.name in self._operations:
            raise ValueError(f"Operation already registered: {operation.name}")
        self._operations[operation.name] = operation
        for clip_type in clip_types or []:
            self._clip_type_operations[clip_type] = operation.name
        return operation

    def unregister(self, name: str) -> None:
        self._operations.pop(name, None)
        self._clip_type_operations = {
            k: v for k, v in self._clip_type_operations.items() if v != name
        }

    def get(self, name: str) -> Operation:
        try:
            return self._operations[name]
        except KeyError as e:
            raise KeyError(f"Unknown operation: {name}") from e

    def has(self, name: str) -> bool:
        return name in self._operations

    def list(self) -> list[Operation]:
        return [self._operations[k] for k in sorted(self._operations)]

    def schemas(self) -> list[dict[str, Any]]:
        return [op.schema() for op in self.list()]

    def map_clip_type(self, clip_type: str, operation_name: str) -> None:
        if operation_name not in self._operations:
            raise KeyError(f"Unknown operation: {operation_name}")
        self._clip_type_operations[clip_type] = operation_name

    def operation_for_clip_type(self, clip_type: str) -> str | None:
        return self._clip_type_operations.get(clip_type)

    def clip_type_mappings(self) -> dict[str, str]:
        return dict(self._clip_type_operations)


# Global default registry used by the app.
registry = OperationRegistry()
