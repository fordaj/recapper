#!/usr/bin/env python3
"""Recapper server: static UI + JSON API."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import traceback
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from recapper.ffmpeg import check_system, probe_media, which
from recapper.jobs import jobs
from recapper.model import MediaAsset, Project, new_id
from recapper.project import DEFAULT_PROJECT_FILENAME, load_project, project_path_for, relativize_asset_path, resolve_asset_path, save_project


ROOT = Path(__file__).resolve().parent
STATE: dict = {
    "workspace": ROOT,
    "project_path": None,  # Path | None
    "project": None,       # Project | None
    "thumb_dir": ROOT / ".recapper-cache" / "thumbs",
}


def _json_bytes(data: object) -> bytes:
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


def _safe_name(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-._")
    return name or "file"


def _get_project() -> Project:
    proj = STATE.get("project")
    if proj is None:
        proj = Project.default("Untitled Recap")
        STATE["project"] = proj
    return proj


def _ensure_thumb_dir() -> Path:
    d: Path = STATE["thumb_dir"]
    d.mkdir(parents=True, exist_ok=True)
    return d


def _thumb_for_media(asset: MediaAsset) -> str | None:
    """Generate or return a thumbnail/still URL path for a media asset."""
    src = _resolve_media_path(asset)
    if not src.exists():
        return None
    _ensure_thumb_dir()
    thumb_name = f"{asset.id}.jpg"
    thumb_path = _ensure_thumb_dir() / thumb_name
    if thumb_path.exists():
        return f"/api/media/thumb/{asset.id}"

    ffmpeg_path = which("ffmpeg")
    if not ffmpeg_path:
        return None

    if asset.type == "image":
        cmd = [ffmpeg_path, "-y", "-i", str(src), "-vf", "scale=480:-1", "-frames:v", "1", str(thumb_path)]
    elif asset.type == "video":
        # Seek a bit in if possible
        seek = "0.5"
        cmd = [ffmpeg_path, "-y", "-ss", seek, "-i", str(src), "-vf", "scale=480:-1", "-frames:v", "1", str(thumb_path)]
    else:
        return None

    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        if proc.returncode != 0 or not thumb_path.exists():
            return None
    except Exception:
        return None
    return f"/api/media/thumb/{asset.id}"


def _resolve_media_path(asset: MediaAsset) -> Path:
    p = Path(asset.path).expanduser()
    if p.is_absolute():
        return p.resolve()
    proj_path = STATE.get("project_path")
    if proj_path:
        return resolve_asset_path(proj_path, p)
    return (Path(STATE["workspace"]) / p).resolve()


def _register_media_path(path: str | Path, name: str | None = None) -> dict:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"Media file not found: {p}")
    probe = probe_media(p)
    proj = _get_project()
    # Reuse existing asset by resolved path if present
    for existing in proj.media:
        try:
            if _resolve_media_path(existing) == p:
                existing.probe = {k: v for k, v in probe.items() if k != "raw"}
                existing.duration = probe.get("duration")
                existing.width = probe.get("width")
                existing.height = probe.get("height")
                existing.has_audio = probe.get("has_audio")
                existing.codec = probe.get("codec")
                existing.thumbnail = _thumb_for_media(existing)
                return existing.to_dict()
        except Exception:
            pass

    proj_path = STATE.get("project_path")
    stored_path = relativize_asset_path(proj_path, p) if proj_path else str(p)
    asset = MediaAsset(
        id=new_id("m"),
        type=probe.get("type") or "image",
        name=name or p.stem,
        path=stored_path,
        duration=probe.get("duration"),
        width=probe.get("width"),
        height=probe.get("height"),
        has_audio=probe.get("has_audio"),
        codec=probe.get("codec"),
        probe={k: v for k, v in probe.items() if k != "raw"},
    )
    asset.thumbnail = _thumb_for_media(asset)
    proj.media.append(asset)
    proj.touch()
    return asset.to_dict()


class RecapperHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str | None = None, **kwargs):
        super().__init__(*args, directory=directory or str(ROOT), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[server] {self.address_string()} - {fmt % args}\n")

    # ---------- helpers ----------
    def _send_json(self, data: object, status: int = 200) -> None:
        body = _json_bytes(data)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, status: int, message: str, details: object = None) -> None:
        payload = {"error": {"message": message, "status": status}}
        if details is not None:
            payload["error"]["details"] = details
        self._send_json(payload, status=status)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return b""
        return self.rfile.read(length)

    def _read_json(self) -> dict:
        body = self._read_body()
        if not body:
            return {}
        try:
            data = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON body: {e}") from e
        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object")
        return data

    def _parse_url(self):
        parsed = urlparse(self.path)
        query = {k: v[0] if len(v) == 1 else v for k, v in parse_qs(parsed.query).items()}
        return parsed.path, query

    # ---------- routing ----------
    def do_GET(self) -> None:  # noqa: N802
        path, query = self._parse_url()
        if path.startswith("/api/"):
            try:
                self._handle_api_get(path, query)
            except FileNotFoundError as e:
                self._send_error_json(404, str(e))
            except ValueError as e:
                self._send_error_json(400, str(e))
            except Exception as e:
                traceback.print_exc()
                self._send_error_json(500, "Internal server error", str(e))
            return
        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        path, query = self._parse_url()
        if path.startswith("/api/"):
            try:
                self._handle_api_post(path, query)
            except FileNotFoundError as e:
                self._send_error_json(404, str(e))
            except ValueError as e:
                self._send_error_json(400, str(e))
            except Exception as e:
                traceback.print_exc()
                self._send_error_json(500, "Internal server error", str(e))
            return
        self._send_error_json(404, "Not found")

    def do_PUT(self) -> None:  # noqa: N802
        path, query = self._parse_url()
        if path.startswith("/api/"):
            try:
                self._handle_api_put(path, query)
            except FileNotFoundError as e:
                self._send_error_json(404, str(e))
            except ValueError as e:
                self._send_error_json(400, str(e))
            except Exception as e:
                traceback.print_exc()
                self._send_error_json(500, "Internal server error", str(e))
            return
        self._send_error_json(404, "Not found")

    # ---------- API GET ----------
    def _handle_api_get(self, path: str, query: dict) -> None:
        if path == "/api/system/check":
            return self._send_json(check_system())

        if path == "/api/project":
            proj = _get_project()
            return self._send_json({"project": proj.to_dict(), "path": str(STATE["project_path"]) if STATE["project_path"] else None})

        if path == "/api/media":
            proj = _get_project()
            # refresh thumbnails lazily
            for m in proj.media:
                if not m.thumbnail:
                    m.thumbnail = _thumb_for_media(m)
            return self._send_json({"media": [m.to_dict() for m in proj.media]})

        m = re.match(r"^/api/media/thumb/([A-Za-z0-9_-]+)$", path)
        if m:
            asset_id = m.group(1)
            thumb = _ensure_thumb_dir() / f"{asset_id}.jpg"
            if not thumb.exists():
                return self._send_error_json(404, "Thumbnail not found")
            data = thumb.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return

        m = re.match(r"^/api/media/file/([A-Za-z0-9_-]+)$", path)
        if m:
            asset_id = m.group(1)
            proj = _get_project()
            asset = next((a for a in proj.media if a.id == asset_id), None)
            if not asset:
                return self._send_error_json(404, "Media not found")
            p = _resolve_media_path(asset)
            if not p.exists():
                return self._send_error_json(404, f"Media file missing: {p}")
            ctype, _ = mimetypes.guess_type(str(p))
            data = p.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype or "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return

        if path == "/api/jobs":
            return self._send_json({"jobs": [j.to_dict(include_logs=False) for j in jobs.list()]})

        m = re.match(r"^/api/jobs/([A-Za-z0-9_-]+)$", path)
        if m:
            job = jobs.get(m.group(1))
            if not job:
                return self._send_error_json(404, "Job not found")
            return self._send_json({"job": job.to_dict(include_logs=True)})

        m = re.match(r"^/api/export/download/([A-Za-z0-9_-]+)$", path)
        if m:
            job = jobs.get(m.group(1))
            if not job:
                return self._send_error_json(404, "Job not found")
            out = job.result.get("output_path")
            if not out:
                return self._send_error_json(404, "Job has no output")
            p = Path(out)
            if not p.exists():
                return self._send_error_json(404, f"Output missing: {p}")
            ctype, _ = mimetypes.guess_type(str(p))
            data = p.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype or "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Disposition", f'attachment; filename="{p.name}"')
            self.end_headers()
            self.wfile.write(data)
            return

        return self._send_error_json(404, f"Unknown API route: {path}")

    # ---------- API POST ----------
    def _handle_api_post(self, path: str, query: dict) -> None:
        if path == "/api/project/new":
            body = self._read_json()
            name = str(body.get("name") or "Untitled Recap")
            proj = Project.default(name)
            STATE["project"] = proj
            STATE["project_path"] = None
            return self._send_json({"project": proj.to_dict(), "path": None})

        if path == "/api/project/load":
            body = self._read_json()
            p = body.get("path")
            if not p:
                raise ValueError("path is required")
            proj_path = Path(p).expanduser().resolve()
            proj = load_project(proj_path)
            STATE["project"] = proj
            STATE["project_path"] = proj_path
            STATE["workspace"] = proj_path.parent
            # Refresh thumbnails
            for m in proj.media:
                m.thumbnail = _thumb_for_media(m)
            return self._send_json({"project": proj.to_dict(), "path": str(proj_path)})

        if path == "/api/project/save":
            body = self._read_json()
            proj = _get_project()
            # Allow updating project from body
            if "project" in body and isinstance(body["project"], dict):
                proj = Project.from_dict(body["project"])
                STATE["project"] = proj
            p = body.get("path")
            if p:
                proj_path = Path(p).expanduser().resolve()
            else:
                proj_path = STATE.get("project_path")
            if not proj_path:
                workspace = Path(body.get("workspace") or STATE["workspace"]).expanduser().resolve()
                workspace.mkdir(parents=True, exist_ok=True)
                proj_path = project_path_for(workspace)
            save_project(proj, proj_path, strict_media=False)
            STATE["project_path"] = proj_path
            STATE["workspace"] = proj_path.parent
            return self._send_json({"project": proj.to_dict(), "path": str(proj_path)})

        if path == "/api/media/register":
            body = self._read_json()
            p = body.get("path")
            if not p:
                raise ValueError("path is required")
            asset = _register_media_path(p, name=body.get("name"))
            return self._send_json({"media": asset})

        if path == "/api/media/upload":
            # Simple upload: raw body with ?name= or X-Filename header
            filename = self.headers.get("X-Filename") or query.get("name") or "upload"
            filename = _safe_name(str(filename))
            body = self._read_body()
            if not body:
                raise ValueError("Empty upload body")
            uploads = Path(STATE["workspace"]) / "uploads"
            uploads.mkdir(parents=True, exist_ok=True)
            dest = uploads / filename
            # avoid overwrite
            if dest.exists():
                stem, suf = dest.stem, dest.suffix
                dest = uploads / f"{stem}-{new_id('u')}{suf}"
            dest.write_bytes(body)
            asset = _register_media_path(dest, name=Path(filename).stem)
            return self._send_json({"media": asset})

        if path == "/api/media/probe":
            body = self._read_json()
            p = body.get("path")
            if not p:
                raise ValueError("path is required")
            pp = Path(p).expanduser().resolve()
            probe = probe_media(pp)
            probe.pop("raw", None)
            return self._send_json({"probe": probe})

        if path == "/api/render/export":
            body = self._read_json()
            proj = _get_project()
            if "project" in body and isinstance(body["project"], dict):
                proj = Project.from_dict(body["project"])
                STATE["project"] = proj
            # Create a job; actual render pipeline is implemented in Task 4.
            job = jobs.create("export", message="Export queued")

            def run_export(j):
                # Placeholder until Task 4 wires the real pipeline.
                j.update(stage="not_implemented", progress=0, message="Render pipeline not implemented yet")
                j.log("Render/export pipeline will be implemented in Task 4.")
                raise RuntimeError("Render pipeline not implemented yet. Complete Task 4 to enable export.")

            jobs.start(job, run_export)
            return self._send_json({"job": job.to_dict(include_logs=False)})

        return self._send_error_json(404, f"Unknown API route: {path}")

    # ---------- API PUT ----------
    def _handle_api_put(self, path: str, query: dict) -> None:
        if path == "/api/project":
            body = self._read_json()
            if "project" not in body or not isinstance(body["project"], dict):
                raise ValueError("project object is required")
            proj = Project.from_dict(body["project"])
            proj.validate(strict_media=False)
            STATE["project"] = proj
            return self._send_json({"project": proj.to_dict(), "path": str(STATE["project_path"]) if STATE["project_path"] else None})
        return self._send_error_json(404, f"Unknown API route: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the Recapper editor")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", default=8000, type=int, help="Port to bind")
    parser.add_argument("--workspace", default=str(ROOT), help="Workspace directory")
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    STATE["workspace"] = workspace
    STATE["thumb_dir"] = workspace / ".recapper-cache" / "thumbs"

    server = ThreadingHTTPServer((args.host, args.port), RecapperHandler)
    print(f"Recapper editor running at http://{args.host}:{args.port}")
    print(f"Workspace: {workspace}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
