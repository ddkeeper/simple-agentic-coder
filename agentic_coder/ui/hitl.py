"""Human-in-the-Loop approval for tool calls.

Policy:
- read_file, list_files: always allowed (any path)
- write_file, edit_file: allowed if inside CWD; HITL confirm if outside
- run_command: HITL confirm if command contains dangerous patterns
- Persisted permissions (via State) bypass HITL entirely
"""

from __future__ import annotations

from pathlib import Path


def _get_workdir() -> Path:
    return Path.cwd().resolve()

DANGEROUS_CMD_PATTERNS = [
    "rm -rf", "sudo", "shutdown", "reboot", "> /dev/",
    "mkfs", "dd if=", "git push --force", "git reset --hard",
]

WRITE_TOOLS = {"write_file", "edit_file"}


def _is_external_path(path_str: str) -> bool:
    try:
        resolved = Path(path_str).expanduser().resolve()
        return not resolved.is_relative_to(_get_workdir())
    except (OSError, ValueError):
        return False


def _build_pattern(tool_name: str, tool_input: dict) -> str:
    if tool_name in WRITE_TOOLS:
        path = tool_input.get("path", "")
        return str(Path(path).expanduser().resolve()) if path else ""
    if tool_name == "run_command":
        return tool_input.get("command", "")[:100]
    return ""


def check_approval(tool_name: str, tool_input: dict) -> bool:
    """Check if a tool call needs user approval."""
    # Check persisted permissions first
    try:
        from agentic_coder.core.state import get_state
        state = get_state()
        pattern = _build_pattern(tool_name, tool_input)
        key = f"{tool_name}:{pattern}"
        if key in state.permissions:
            return True
    except RuntimeError:
        pass

    # Write tools: confirm if path is outside CWD
    if tool_name in WRITE_TOOLS:
        path = tool_input.get("path", "")
        if path and _is_external_path(path):
            resolved = str(Path(path).expanduser().resolve())
            return _ask_user(f"Write to external path: {path}", tool_name, resolved)

    # run_command: confirm if command contains dangerous patterns
    if tool_name == "run_command":
        command = tool_input.get("command", "")
        if any(p in command for p in DANGEROUS_CMD_PATTERNS):
            return _ask_user(f"Run dangerous command: {command[:100]}", tool_name, command[:100])

    return True


def _ask_user(detail: str, tool_name: str = "", pattern: str = "") -> bool:
    """Prompt user for approval. Returns True if approved."""
    try:
        answer = input(f"\033[33m  Approve? {detail} [y/N/a(lways)]: \033[0m").strip().lower()
        if answer in ("a", "always"):
            if tool_name and pattern:
                from agentic_coder.core.state import add_permission
                add_permission(tool_name, pattern, description=detail)
            return True
        return answer in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False
