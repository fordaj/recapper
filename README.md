# Recapper

A local Python timeline editor for creating family recap videos with FFmpeg.

## Run

```bash
python3 server.py
```

Open <http://127.0.0.1:8000>.

Requirements: `ffmpeg` and `ffprobe` available on `PATH`.

## What it does

- **Media Library**: import local photos/videos/audio, probe metadata with ffprobe, generate thumbnails.
- **Timeline**: multi-track timeline with drag/drop, trim, reorder, playhead, zoom.
- **Preview**: preview selected clip or playhead position for images, videos, titles, and compositions.
- **Inspector**: edit clip timing, title text, composition inputs, volume, and accent.
- **Export**: compile timeline into FFmpeg operations and render an mp4 asynchronously with progress/logs.

## Project model

Projects are stored as JSON (`.recapper.json` by default). Asset paths are relative to the project file when possible, otherwise absolute. See:

- `docs/project-model.md`
- `schema/project.schema.json`
- `examples/demo.recapper.json` (sample project; open by path in UI)

## Extensible operations

Adding a new `name + ffmpeg operation` should only require registering an operation definition. See `docs/adding-operations.md`.

Built-in operations:

| Clip type | Operation | Capability |
|---|---|---|
| `title` | `title-slide` | generates visual |
| `image` | `image-to-video` | generates visual |
| `composition` | `images-to-side-by-side-video` | composes |
| `video` | `normalize-video` | transforms visual |
| `audio` | `audio-track` | mixes audio |

## Development

Run tests:

```bash
python3 -m unittest discover -s tests -v
```
