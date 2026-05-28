# s10: Complete

> **Key insight**: Split the 9-chapter single-file agent into engineering structure — the last step from teaching code to production code.

## What You Have Now

A complete coding agent with:

| Feature | Source Chapter |
|---------|---------------|
| Agent loop | s01 |
| Tool dispatch | s02 |
| System prompt | s03 |
| Task planning | s04 |
| Subagent | s05 |
| Context compaction | s06 |
| Permission system | s07 |
| Git integration | s08 |
| Background tasks | s09 |

## Engineering Structure

Split from single file to modules:

```
final/
├── __main__.py         # CLI entry point
├── loop.py             # agent loop core (~60 lines)
├── tools/
│   ├── __init__.py     # TOOLS list + TOOL_HANDLERS
│   ├── bash.py         # bash + background tasks
│   ├── files.py        # read / write / edit / find
│   ├── todo.py         # TodoManager
│   ├── task.py         # subagent
│   └── git.py          # auto commit
├── permissions.py      # permission tiers
├── compaction.py       # context compression
└── config.py           # CLI args + env vars
```

## Module Relationships

```
__main__.py
    |
    v
loop.py  ─────────────────────┐
    |                          |
    +---> tools/bash.py        |
    +---> tools/files.py       |
    +---> tools/todo.py        |  called by loop
    +---> tools/task.py        |
    +---> tools/git.py         |
    |                          |
    +---> permissions.py ──────┘
    +---> compaction.py
    +---> config.py
```

`loop.py` is the center; all other modules are tools or strategies it calls.

## Evolution from s01 to s10

```
s01:  80 lines, one file, one tool
s02:  +120 lines, dispatch map
s03:  +30 lines, system prompt
s04:  +80 lines, TodoManager
s05:  +60 lines, task tool
s06:  +50 lines, compact
s07:  +40 lines, permission
s08:  +50 lines, git
s09:  +60 lines, background
s10:  split into 10 files, each <100 lines
```

## What's Still Missing vs Production Agents

This agent covers ~80% of Claude Code's core mechanisms, but we deliberately omitted some production features:

| Omitted Feature | Why Omitted |
|----------------|-------------|
| Hook system | Event hooks, not core loop component |
| MCP Server | External tool protocol, extends "tools" at architecture level |
| Memory files | Persistent memory, simple file I/O |
| Cron Scheduler | Scheduled tasks, independent of agent loop |
| Streaming | UX optimization, not architectural |
| Multi-model support | Configuration issue, not architecture |

These can be added one by one after the core architecture is understood.

## Try It

```bash
python -m final
```

Recommended prompts:

1. `Create a Python project with a main module and utility functions`
2. `Add tests using pytest, run them in the background, and fix any failures`
3. `Refactor the project: move utility functions into a separate package`
4. `Review all files, check git log, and summarize what we built`
