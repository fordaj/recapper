# Adding a new ffmpeg operation

Recapper operations are registered by name in `recapper.ops.registry.registry`. The goal is that adding a new `name + ffmpeg operation` requires only one operation definition and one registration.

## 1. Implement the operation

Create a module in `recapper/ops/`, for example `recapper/ops/ken_burns.py`:

```python
from recapper.ffmpeg import run_ffmpeg, which
from .base import Operation, OperationCapability, OperationField, OperationResult, RenderContext

class KenBurnsOperation(Operation):
    name = "ken-burns"
    description = "Animate a still image with a pan/zoom effect."
    capability = OperationCapability.GENERATES_VISUAL

    input_schema = [
        OperationField("image", "asset", required=True, description="Image asset ID or path"),
    ]
    params_schema = [
        OperationField("duration", "number", required=True, default=5, min=0.5, ui_label="Duration (s)"),
        OperationField("zoom", "number", required=False, default=1.1, min=1.0, max=2.0),
        OperationField("width", "integer", required=False, default=1920, min=16),
        OperationField("height", "integer", required=False, default=1080, min=16),
        OperationField("fps", "integer", required=False, default=30, min=1, max=120),
        OperationField("output", "string", required=False, default=""),
    ]
    default_params = {f.name: f.default for f in params_schema if f.default is not None}

    def build(self, inputs, params, context: RenderContext) -> OperationResult:
        p = self.validate(inputs, params)
        ffmpeg = which("ffmpeg")
        # Resolve input, build ffmpeg command, run_ffmpeg(cmd), return outputs/commands.
        ...
```

## 2. Register it

Add it to `recapper/ops/builtins.py` (or register at startup):

```python
from .ken_burns import KenBurnsOperation

BUILTIN_OPERATIONS.append(KenBurnsOperation())
CLIP_TYPE_OPERATION_MAP["ken-burns"] = "ken-burns"  # if it maps to a clip type
```

`register_builtin_operations()` registers operations and clip-type mappings in the global registry.

## 3. Timeline/UI mapping (optional)

If the operation corresponds to a timeline clip type, map it in `CLIP_TYPE_OPERATION_MAP` and ensure the frontend knows how to create/edit that clip type. The backend registry exposes schemas via `GET /api/operations`.

## Contract

- `name`: stable operation identifier.
- `capability`: `generates_visual`, `generates_audio`, `transforms_visual`, `transforms_audio`, `composes`, or `mixes_audio`.
- `input_schema` / `params_schema`: declarative fields used for validation and UI metadata.
- `build(inputs, params, context)`: returns `OperationResult(outputs=[...], commands=[...], artifacts={...})`. It should raise on failure.
- `RenderContext` provides `project_dir`, `temp_dir`, `output_dir`, `render_settings`, and resolved `assets`.

## Tests

Add a unit test that mocks `run_ffmpeg` and asserts the generated command contains the expected ffmpeg filters/args. See `tests/test_ops.py`.
