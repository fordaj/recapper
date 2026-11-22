"""Project persistence and path resolution.

Persistence format: JSON file, default name `.recapper.json`.
Location: inside a project workspace directory chosen by the user. Asset paths
are stored as relative paths when they are inside the project directory,
otherwise as absolute paths. This keeps projects portable when media lives with
the project, while still allowing users to reference external media.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from .model import Project

DEFAULT_PROJECT_FILENAME = ".recapper.json"


def project_path_for(directory: str | Path, filename: str = DEFAULT_PROJECT_FILENAME) -> Path:
    d = Path(directory).expanduser().resolve()
    return d / filename


def load_project(path: str | Path) -> Project:
    p = Path(path).expanduser().resolve()
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Project file must contain a JSON object")
    project = Project.from_dict(data)
    return project


def save_project(project: Project, path: str | Path, *, strict_media: bool = False) -> Path:
    p = Path(path).expanduser().resolve()
    project.validate(strict_media=strict_media)
    project.touch()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(project.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(p)
    return p


def resolve_asset_path(project_file: str | Path, asset_path: str | Path) -> Path:
    """Resolve an asset path from a project file location."""
    base = Path(project_file).expanduser().resolve().parent
    p = Path(asset_path).expanduser()
    if not p.is_absolute():
        p = (base / p).resolve()
    return p


def relativize_asset_path(project_file: str | Path, asset_path: str | Path) -> str:
    """Store path relative to project dir when possible, else absolute."""
    base = Path(project_file).expanduser().resolve().parent
    p = Path(asset_path).expanduser().resolve()
    try:
        return str(p.relative_to(base))
    except ValueError:
        return str(p)


def export_project_schema(project: Project) -> dict[str, Any]:
    """Convenience for API responses/debugging."""
    return project.to_dict()
