"""File system tools.

Read operations: any path allowed.
Write operations: any path allowed, HITL controls dangerous writes.
"""

from __future__ import annotations

from pathlib import Path

from tools.registry import tool


@tool("Read the contents of a file. Returns the full text or up to 'limit' lines.")
def read_file(path: str, limit: int | None = None) -> str:
    text = Path(path).expanduser().resolve().read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    if limit and limit < len(lines):
        lines = lines[:limit] + [f"\n... ({len(lines) - limit} more lines)"]
    return "\n".join(lines)[:50000]


@tool("Write content to a file, creating directories as needed. Overwrites existing files.", dangerous=True)
def write_file(path: str, content: str) -> str:
    fp = Path(path).expanduser().resolve()
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} bytes to {fp}"


@tool("Replace the first occurrence of old_text with new_text in a file.", dangerous=True)
def edit_file(path: str, old_text: str, new_text: str) -> str:
    fp = Path(path).expanduser().resolve()
    content = fp.read_text(encoding="utf-8")
    if old_text not in content:
        return f"Error: old_text not found in {path}"
    fp.write_text(content.replace(old_text, new_text, 1), encoding="utf-8")
    return f"Edited {fp}"


@tool("List files and directories in a path. Shows [d] for dirs, [f] for files.")
def list_files(path: str = ".") -> str:
    target = Path(path).expanduser().resolve()
    entries = sorted(target.iterdir())
    lines = []
    for e in entries[:100]:
        prefix = "[d]" if e.is_dir() else "[f]"
        lines.append(f"{prefix} {e}")
    if len(entries) > 100:
        lines.append(f"... ({len(entries) - 100} more)")
    return "\n".join(lines) if lines else "(empty directory)"
