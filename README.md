# Recapper

A Python server and timeline-first video editor prototype for creating family recap videos.

## Timeline Editor Prototype

This branch includes a working timeline-editor UI prototype based on the pitch in `TODO.md`.

### Run

```bash
python3 server.py
```

Then open <http://127.0.0.1:8000>.

### What’s included

- **Preview**: Prominent preview for the selected clip or playhead position.
- **Media Library**: Sample photos, videos, and audio items with drag-to-timeline support.
- **Properties Inspector**: Context-sensitive controls for clip name, timing, title text, composition, volume, and accent.
- **Timeline**: Horizontal multi-track timeline with ruler, playhead, clip selection, trimming, drag reordering, and zoom.

### Notes

- This is a UI prototype focused on the editing experience described in `TODO.md`.
- Export and some media behaviors are demo placeholders.
