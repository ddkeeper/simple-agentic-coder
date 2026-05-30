"""Human-in-the-Loop approval for tool calls.

Policy:
- read_file, list_files: always allowed (any path)
- write_file, edit_file: allowed if inside CWD; HITL confirm if outside
- run_command: HITL confirm if command contains dangerous patterns
"""

from __future__ import annotations

from pathlib import Path

WORKDIR = Path.cwd().resolve()

DANGEROUS_CMD_PATTERNS = [
    "rm -rf", "sudo", "shutdown", "reboot", "> /dev/",
    "mkfs", "dd if=", "git push --force", "git reset --hard",
]

# Tools that modify the filesystem
WRITE_TOOLS = {"write_file", "edit_file"}


def _is_external_path(path_str: str) -> bool:
    """Check if a path resolves to somewhere outside the working directory."""
    try:
        resolved = Path(path_str).expanduser().resolve()
        return not resolved.is_relative_to(WORKDIR)
    except (OSError, ValueError):
        return False


def check_approval(tool_name: str, tool_input: dict) -> bool:
    """Check if a tool call needs user approval.

    Returns True if approved (or no approval needed), False if denied.
    """
    # --- Write tools: confirm if path is outside CWD ---
    if tool_name in WRITE_TOOLS:
        path = tool_input.get("path", "")
        if path and _is_external_path(path):
            return _ask_user(f"Write to external path: {path}")

    # --- run_command: confirm if command contains dangerous patterns ---
    if tool_name == "run_command":
        command = tool_input.get("command", "")
        if any(p in command for p in DANGEROUS_CMD_PATTERNS):
            return _ask_user(f"Run dangerous command: {command[:100]}")

    return True


def _ask_user(detail: str) -> bool:
    """Prompt user for approval. Returns True if approved."""
    try:
        answer = input(f"\033[33m  Approve? {detail} [y/N]: \033[0m").strip().lower()
        return answer in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False
