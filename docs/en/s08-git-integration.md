# s08: Git Integration

> **Key insight**: A coding agent and Git are natural symbionts — every change having version history is the foundation of trust.

## The Problem

After the agent edits files, users don't know what changed, when, or why. Manual `git add && git commit` is tedious, and the agent often forgets to commit. Without version control, every agent modification is an irreversible gamble.

## The Solution

After `edit_file` and `write_file` complete, automatically run git commit.

```
User: "Add error handling to utils.py"
  |
  v
Agent edits utils.py
  |
  v
auto: git add utils.py && git commit -m "Add error handling to utils.py"
  |
  v
Agent reports: "Done. Committed as abc1234"
```

## How It Works

1. Trigger auto-commit after file writes.

```python
def run_edit(path, old_text, new_text, io):
    # ... do the edit ...
    result = f"Edited {path}"
    git_auto_commit(path, f"Edit {path}", io)
    return result
```

2. Auto-commit function: only stages the modified file, doesn't pollute other changes.

```python
def git_auto_commit(filepath, message, io):
    try:
        repo = git.Repo(search_parent_directories=True)
        rel = os.path.relpath(filepath, repo.working_tree_dir)
        repo.index.add([rel])
        repo.index.commit(f"[agent] {message}")
    except git.InvalidGitRepositoryError:
        pass  # not a git repo, skip
    except Exception as e:
        io.print(f"Git commit failed: {e}")
```

3. Diff summary injection: append git diff to tool_result so the model sees consequences of its edits.

```python
def append_diff_summary(tool_result, repo):
    diff = repo.git.diff("HEAD~1", "--stat")
    tool_result += f"\n[git diff --stat]\n{diff}"
    return tool_result
```

## Why Not Auto-Push

- Push affects remote — irreversible
- Users may want to review first
- CI/CD may handle push automatically

Auto-commit is local, safe, and reversible (`git reset`).

## What Changed from s07

| Component    | s07           | s08                                |
|-------------|---------------|------------------------------------|
| File editing | Write only   | Write + auto commit               |
| Git ops     | None          | `git_auto_commit()`               |
| Diff inject | None          | Append diff stat to tool_result   |
| Agent loop  | Unchanged     | Unchanged                          |

## Try It

```bash
python agents/s08_git_integration.py
```

Recommended prompts:

1. `Create a new file called config.py with a DEBUG constant`
2. `Edit config.py to set DEBUG = False`
3. `Run git log` — should see agent's auto commits
4. `Run git diff HEAD~1` — view latest commit changes
