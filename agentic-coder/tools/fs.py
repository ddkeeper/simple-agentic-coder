"""File system tools.

Read operations: any path allowed.
Write operations: any path allowed, HITL controls dangerous writes.
"""

from __future__ import annotations

import re
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


@tool("Search for files matching a glob pattern (e.g. '**/*.py', 'src/**/*.ts'). Returns up to 200 paths.")
def glob_search(pattern: str, path: str = ".") -> str:
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        return f"Error: '{path}' is not a directory"
    try:
        matches = sorted(root.glob(pattern))
    except (ValueError, re.error) as e:
        return f"Error: invalid pattern '{pattern}': {e}"
    if not matches:
        return "(no matches)"
    paths = [str(m.relative_to(root)) for m in matches[:200]]
    result = "\n".join(paths)
    if len(matches) > 200:
        result += f"\n... ({len(matches) - 200} more matches)"
    return result


@tool("Search file contents for a regex pattern. Returns matching lines with file:line:content format.")
def grep_search(pattern: str, path: str = ".", glob: str = "*.py") -> str:
    target = Path(path).expanduser().resolve()
    if target.is_file():
        files = [target]
    elif target.is_dir():
        files = sorted(target.rglob(glob))
    else:
        return f"Error: '{path}' does not exist"
    try:
        regex = re.compile(pattern)
    except re.error as e:
        return f"Error: invalid regex '{pattern}': {e}"
    MAX_LINES = 100
    MAX_LINE_LEN = 200
    matches: list[str] = []
    for fp in files:
        if not fp.is_file():
            continue
        try:
            if fp.stat().st_size > 1_000_000:
                continue
            text = fp.read_text(encoding="utf-8", errors="ignore")
        except (OSError, PermissionError):
            continue
        for line_num, line in enumerate(text.splitlines(), 1):
            if regex.search(line):
                rel_path = str(fp.relative_to(target)) if target.is_dir() else fp.name
                display_line = line[:MAX_LINE_LEN] + ("..." if len(line) > MAX_LINE_LEN else "")
                matches.append(f"{rel_path}:{line_num}: {display_line}")
                if len(matches) >= MAX_LINES:
                    matches.append(f"... (truncated at {MAX_LINES} lines)")
                    return "\n".join(matches)
    return "\n".join(matches) if matches else "(no matches)"
