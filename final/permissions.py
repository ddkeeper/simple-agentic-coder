#!/usr/bin/env python3
"""Permission system — tiered tool execution control."""

PERMISSIONS = {
    "read_file": "auto",
    "find_files": "auto",
    "git_log": "auto",
    "write_file": "ask",
    "edit_file": "ask",
    "bash": "ask",
    "todo": "auto",
    "task": "auto",
    "task_output": "auto",
}

READONLY_BASH_PREFIXES = [
    "ls", "cat", "head", "tail", "pwd", "echo",
    "git status", "git log", "git diff", "which",
]


def check_permission(tool_name: str, tool_input: dict, config: dict) -> tuple[bool, str]:
    """Returns (allowed, reason)."""
    if config.get("auto_approve"):
        return True, "auto-approved (--yes)"

    level = PERMISSIONS.get(tool_name, "ask")

    if level == "deny":
        return False, f"{tool_name} is not allowed"

    if level == "auto":
        return True, "auto"

    # "ask" tier — special handling for bash
    if tool_name == "bash":
        command = tool_input.get("command", "")
        if any(command.strip().startswith(p) for p in READONLY_BASH_PREFIXES):
            return True, "read-only command"

    return True, "needs confirmation"


def confirm_tool(tool_name: str, tool_input: dict) -> bool:
    """Prompt user for confirmation. Returns True if approved."""
    summary = str(tool_input)
    if len(summary) > 100:
        summary = summary[:100] + "..."
    try:
        answer = input(f"\033[33m  {tool_name}: {summary} [y/n] \033[0m").strip().lower()
        return answer in ("y", "yes", "")
    except (EOFError, KeyboardInterrupt):
        return False
