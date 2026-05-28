#!/usr/bin/env python3
"""Git tools — auto-commit and git log."""

import os

try:
    import git as gitmodule
except ImportError:
    gitmodule = None


def git_auto_commit(filepath: str, message: str) -> str | None:
    """Stage and commit a single file. Returns commit hash or None."""
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


def run_git_log(count: int = 5) -> str:
    if gitmodule is None:
        return "Error: gitpython not installed"
    try:
        repo = gitmodule.Repo(search_parent_directories=True)
        commits = list(repo.iter_commits(max_count=count))
        lines = []
        for c in commits:
            lines.append(f"{c.hexsha[:7]} {c.message.strip()}")
        return "\n".join(lines) if lines else "(no commits)"
    except Exception as e:
        return f"Error: {e}"
