"""Shell command execution tool."""

from __future__ import annotations

import subprocess
from pathlib import Path

from tools.registry import tool

DANGEROUS_PATTERNS = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/", "mkfs", "dd if="]


@tool("Run a shell command and return stdout + stderr.", dangerous=True)
def run_command(command: str) -> str:
    if any(d in command for d in DANGEROUS_PATTERNS):
        return "Error: Dangerous command blocked"
    try:
        r = subprocess.run(
            command, shell=True, cwd=str(Path.cwd()),
            capture_output=True, text=True, timeout=120,
        )
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out (120s)"
    except (FileNotFoundError, OSError) as e:
        return f"Error: {e}"
