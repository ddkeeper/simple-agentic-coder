"""Git tools: log, auto-commit, branch info."""

from __future__ import annotations

import os

from agentic_coder.tools.registry import tool

try:
    import git as gitmodule
except ImportError:
    gitmodule = None


@tool("Show recent git log entries.")
def git_log(count: int = 5) -> str:
    if gitmodule is None:
        return "Error: gitpython not installed"
    try:
        repo = gitmodule.Repo(search_parent_directories=True)
        commits = list(repo.iter_commits(max_count=count))
        lines = [f"{c.hexsha[:7]} {c.message.strip()}" for c in commits]
        return "\n".join(lines) if lines else "(no commits)"
    except Exception as e:
        return f"Error: {e}"


def git_auto_commit(filepath: str, message: str) -> str | None:
    """Stage and commit a single file. Returns short hash or None.

    This is NOT a @tool — called by the engine layer, not the LLM.
    """
    if gitmodule is None:
        return None
    try:
        repo = gitmodule.Repo(search_parent_directories=True)
        rel = os.path.relpath(filepath, repo.working_tree_dir)
        repo.index.add([rel])
        commit = repo.index.commit(f"[agent] {message}")
        return str(commit.hexsha[:7])
    except Exception:
        return None


def get_current_branch() -> str:
    """Get current git branch name. Returns 'unknown' if not in a repo."""
    try:
        r = __import__("subprocess").run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip() or "unknown"
    except Exception:
        return "unknown"
