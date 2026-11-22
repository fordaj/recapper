# Recapper project model and operation contract

## Persistence format

- **Format**: JSON.
- **Default filename**: `.recapper.json`.
- **Location**: a user-chosen project workspace directory. The project file lives in that directory.
- **Asset paths**: stored relative to the project file when the asset is inside the project directory; otherwise stored as an absolute path. This keeps projects portable when media is colocated, while still allowing external media.
- **Save behavior**: validate, update `updated_at`, write atomically via temp file + rename.

See `schema/project.schema.json` for the JSON Schema and `recapper/model.py` for the canonical Python model.

## Timeline/project schema

A project contains:

- `version`, `id`, `name`, timestamps, `meta`
- `media[]`: imported media assets (image/video/audio), with probed metadata
- `tracks[]`: ordered tracks with `kind` (`visual` or `audio`)
- `clips[]`: timeline clips with `trackId`, `start`, `duration`, `type`, `mediaId`, and `params`
- `render`: output/render settings (resolution, fps, codecs, quality, output name)

## Clip type to operation mapping

| UI/Timeline clip type | Operation name | Capability | Notes |
|---|---|---|---|
| `title` | `title-slide` | generates visual | Title/subtitle/background/color/duration |
| `image` | `image-to-video` | generates visual | Still image becomes timed video segment |
| `composition` | `images-to-side-by-side-video` | composes | Two image inputs composed side-by-side |
| `video` | `normalize-video` | transforms visual | User video normalized to render profile |
| `audio` | `audio-track` | mixes audio | Placed/mixed during audio pass |

## Operation contract

Operations are registered in `recapper.ops.registry.registry`. Adding a new `name + ffmpeg operation` should only require:

1. Implement an `Operation` subclass in `recapper/ops/`.
2. Declare `name`, `description`, `capability`, `input_schema`, `params_schema`, and `default_params`.
3. Implement `build(inputs, params, context) -> OperationResult` to produce ffmpeg commands/artifacts.
4. Register it with `register(op, clip_types=[...])` if it maps to a clip type.

The contract lives in `recapper/ops/base.py`; registry in `recapper/ops/registry.py`; built-ins in `recapper/ops/builtins.py`.
