"""Operation registry and built-in operation definitions."""

from .base import Operation, OperationCapability, OperationField, OperationResult, RenderContext
from .registry import OperationRegistry, registry
from .builtins import register_builtin_operations, CLIP_TYPE_OPERATION_MAP

register_builtin_operations(registry)

__all__ = [
    "OperationRegistry",
    "registry",
    "Operation",
    "OperationCapability",
    "OperationField",
    "OperationResult",
    "RenderContext",
    "register_builtin_operations",
    "CLIP_TYPE_OPERATION_MAP",
]
