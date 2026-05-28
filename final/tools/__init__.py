#!/usr/bin/env python3
"""Tool registry — TOOLS list and TOOL_HANDLERS dispatch map."""

from .bash import run_bash, run_task_output
from .files import run_edit, run_find, run_read, run_write
from .git import run_git_log
from .todo import run_todo

TOOLS = [
    {
        "name": "bash",
        "description": "Run a shell command.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "background": {"type": "boolean", "default": False},
            },
            "required": ["command"],
        },
    },
    {
        "name": "read_file",
        "description": "Read file contents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": "Replace exact text in a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_text": {"type": "string"},
                "new_text": {"type": "string"},
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
    {
        "name": "find_files",
        "description": "Find files by name substring (recursive, case-insensitive).",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Substring to match"},
                "path": {"type": "string", "description": "Directory to search, default '.'"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "todo",
        "description": "Update task plan. Only one task can be in_progress at a time.",
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "text": {"type": "string"},
                            "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]},
                        },
                        "required": ["id", "text", "status"],
                    },
                },
            },
            "required": ["items"],
        },
    },
    {
        "name": "task",
        "description": "Spawn a subagent with fresh context for isolated research.",
        "input_schema": {
            "type": "object",
            "properties": {"prompt": {"type": "string"}},
            "required": ["prompt"],
        },
    },
    {
        "name": "task_output",
        "description": "Get the output of a background task.",
        "input_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
    },
    {
        "name": "git_log",
        "description": "Show recent git log.",
        "input_schema": {
            "type": "object",
            "properties": {"count": {"type": "integer", "default": 5}},
        },
    },
]

# Tools available to child subagents (no 'task' to prevent recursion)
CHILD_TOOLS = [t for t in TOOLS if t["name"] != "task"]

# Dispatch map: tool_name -> handler function
TOOL_HANDLERS = {
    "bash": lambda **kw: run_bash(kw["command"], kw.get("background", False), kw.get("config", {})),
    "read_file": lambda **kw: run_read(kw["path"], kw.get("limit")),
    "write_file": lambda **kw: run_write(kw["path"], kw["content"]),
    "edit_file": lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),
    "find_files": lambda **kw: run_find(kw["pattern"], kw.get("path", ".")),
    "todo": lambda **kw: run_todo(kw["items"]),
    "task": lambda **kw: run_bash(kw.get("prompt", ""), config=kw.get("config", {})),  # placeholder
    "task_output": lambda **kw: run_task_output(kw["task_id"]),
    "git_log": lambda **kw: run_git_log(kw.get("count", 5)),
}
