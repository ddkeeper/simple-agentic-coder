"""System prompt builder with dynamic context injection."""

from __future__ import annotations

import os
import platform
from datetime import datetime

from tools.git import get_current_branch


def build_system_prompt() -> str:
    cwd = os.getcwd()

    # Top-level file listing (max 20)
    try:
        entries = sorted(os.listdir(cwd))[:20]
        file_tree = "\n".join(f"  {e}" for e in entries)
    except OSError:
        file_tree = "  (unable to list)"

    branch = get_current_branch()

    return f"""You are a coding agent working in {cwd}.

## Environment
- OS: {platform.system()}
- Date: {datetime.now().strftime("%Y-%m-%d")}
- Git branch: {branch}

## Project Files
{file_tree}

## Capabilities
- Read, write, edit files
- Run shell commands
- List directory contents
- View git history

## Rules
- Act, don't explain. Make changes directly.
- Use tools to verify your work (read after edit).
- Keep working until the task is fully complete.
- Never fabricate file contents — always read first.
"""
