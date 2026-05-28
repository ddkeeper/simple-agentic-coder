#!/usr/bin/env python3
"""Bash tool — execute shell commands with optional background mode."""

import os
import subprocess

TASKS = {}  # {task_id: {"proc": Popen, "status": str}}
COUNTER = 0

DANGEROUS = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
READONLY_PREFIXES = ["ls", "cat", "head", "tail", "pwd", "git status", "git log", "echo"]


def run_bash(command: str, background: bool = False, config: dict = None) -> str:
    config = config or {}
    cwd = config.get("cwd", os.getcwd())

    if any(d in command for d in DANGEROUS):
        return "Error: Dangerous command blocked"

    if not background:
        return _execute_sync(command, cwd)

    return _execute_background(command, cwd)


def _execute_sync(command: str, cwd: str) -> str:
    try:
        r = subprocess.run(
            command, shell=True, cwd=cwd,
            capture_output=True, text=True, timeout=120,
        )
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"
    except (FileNotFoundError, OSError) as e:
        return f"Error: {e}"


def _execute_background(command: str, cwd: str) -> str:
    global COUNTER
    COUNTER += 1
    task_id = f"task_{COUNTER}"

    try:
        proc = subprocess.Popen(
            command, shell=True, cwd=cwd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
    except Exception as e:
        return f"Error: {e}"

    TASKS[task_id] = {"proc": proc, "status": "running"}
    return f"Background task started: {task_id}"


def run_task_output(task_id: str) -> str:
    task = TASKS.get(task_id)
    if not task:
        return f"Error: Unknown task {task_id}"

    proc = task["proc"]
    if proc.poll() is None:
        return f"Task {task_id} still running..."

    stdout, stderr = proc.communicate()
    task["status"] = "done"
    out = (stdout + stderr).strip()
    return f"Exit code: {proc.returncode}\n{out[:50000]}" if out else f"Exit code: {proc.returncode}"
