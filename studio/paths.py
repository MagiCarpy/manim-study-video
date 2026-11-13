"""Portable generation paths, independent of the skill's install location.

Lessons default to ~/study-videos/lessons unless explicitly overridden.
"""

from __future__ import annotations

import os
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent


def lessons_dir(override: str | os.PathLike | None = None) -> Path:
    """Resolve explicit lessons root, environment override, or workspace default."""
    workspace = Path(os.environ.get("STUDY_HOME") or Path.home() / "study-videos")
    d = override or os.environ.get("STUDY_LESSONS_DIR") or workspace / "lessons"
    return Path(d).expanduser().resolve()


def lesson_dir(slug_or_path: str, lessons: str | os.PathLike | None = None) -> Path:
    """`my-slug` -> <lessons>/my-slug; anything that looks like a path is used as-is."""
    if os.sep in slug_or_path or slug_or_path.startswith((".", "~")):
        return Path(slug_or_path).expanduser().resolve()
    return lessons_dir(lessons) / slug_or_path


def rel(p: Path) -> str:
    """Path relative to cwd when it's below it (shorter logs), else absolute."""
    try:
        return str(p.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(p)
