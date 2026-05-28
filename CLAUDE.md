# CLAUDE.md

## Project Overview

An incremental tutorial for building a Claude Code–style AI coding agent in Python.
10 chapters, each a standalone runnable file, from a bare agent loop to a full-featured agent.

## Structure

```
agents/sXX_*.py    — standalone chapter files (each runnable with `python agents/sXX_*.py`)
docs/zh/           — Chinese teaching docs (one per chapter)
docs/en/           — English teaching docs (one per chapter)
final/             — modular engineering version of the complete agent
  loop.py          — core agent loop (never changes across chapters)
  tools/           — tool implementations (bash, files, todo, task, git)
  permissions.py   — tiered permission system
  compaction.py    — context window compression
  config.py        — CLI args and environment config
```

## Development Notes

- Single dependency file: `requirements.txt` (anthropic, python-dotenv)
- Each `agents/sXX_*.py` is fully self-contained — no imports from `final/`
- `final/` is the modular version that imports across submodules
- Default model is set via `MODEL_ID` env var
- Anthropic SDK is used directly (no wrapper libraries)
- Teaching docs mirror between `docs/zh/` and `docs/en/` — keep both in sync when editing

## Running

```bash
export ANTHROPIC_API_KEY="sk-..."
python agents/s01_agent_loop.py        # run a single chapter
python -m final                         # run the modular version
```

## Conventions

- Python 3.10+ (uses `str | None` union syntax)
- No type checker configured — keep annotations lightweight
- Agent loop pattern: `while stop_reason == "tool_use"` — this is the invariant across all chapters
- Each chapter adds exactly one concept; diff between sXX and sXX+1 should be small and reviewable
