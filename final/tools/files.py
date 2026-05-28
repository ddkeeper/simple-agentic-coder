#!/usr/bin/env python3
"""File tools — read, write, edit, find with path sandboxing."""

import os
from pathlib import Path

WORKDIR = Path.cwd()


def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path


def run_read(path: str, limit: int = None) -> str:
    try:
        text = safe_path(path).read_text()
        lines = text.splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
        return "\n".join(lines)[:50000]
    except Exception as e:
        return f"Error: {e}"


def run_write(path: str, content: str) -> str:
    try:
        fp = safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"


def run_edit(path: str, old_text: str, new_text: str) -> str:
    try:
        fp = safe_path(path)
        content = fp.read_text()
        if old_text not in content:
            return f"Error: Text not found in {path}"
        fp.write_text(content.replace(old_text, new_text, 1))
        return f"Edited {path}"
    except Exception as e:
        return f"Error: {e}"


def run_find(pattern: str, path: str = ".") -> str:
    try:
        target = safe_path(path)
        matches = sorted(e for e in target.rglob("*") if pattern.lower() in e.name.lower())
        lines = [f"{'[d]' if e.is_dir() else '[f]'} {e.relative_to(WORKDIR)}" for e in matches]
        return "\n".join(lines)[:50000] if lines else "(no matches)"
    except Exception as e:
        return f"Error: {e}"
