# s08: Git Integration

> **核心洞察**: 编码 agent 天然和 Git 共生——每次改动都有版本记录是信任的基础。

## 问题

Agent 改了文件后，用户不知道改了什么、什么时候改的。手动 `git add && git commit` 太繁琐，而且 agent 经常忘记提交。没有版本控制，agent 的每一次修改都是一次不可逆的赌博。

## 解决方案

在 `edit_file` 和 `write_file` 工具完成后，自动执行 git commit。

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

## 工作原理

1. 文件写入后触发自动提交。

```python
def run_edit(path, old_text, new_text, io):
    # ... do the edit ...
    result = f"Edited {path}"
    git_auto_commit(path, f"Edit {path}", io)
    return result
```

2. 自动提交函数：只提交被修改的文件，不污染其他变更。

```python
def git_auto_commit(filepath, message, io):
    try:
        repo = git.Repo(search_parent_directories=True)
        rel = os.path.relpath(filepath, repo.working_tree_dir)
        repo.index.add([rel])
        repo.index.commit(f"[agent] {message}")
    except git.InvalidGitRepositoryError:
        pass  # 非 git 仓库，跳过
    except Exception as e:
        io.print(f"Git commit failed: {e}")
```

3. Diff 摘要注入：在 agent loop 的 tool_result 后追加 git diff，让模型看到自己的修改后果。

```python
def append_diff_summary(tool_result, repo):
    diff = repo.git.diff("HEAD~1", "--stat")
    tool_result += f"\n[git diff --stat]\n{diff}"
    return tool_result
```

## 为什么不自动 push

- push 影响远端，是不可逆操作
- 用户可能想 review 后再 push
- CI/CD 可能自动处理 push

自动 commit 是本地操作，安全且可逆（`git reset`）。

## 相对 s07 的变更

| 组件         | s07            | s08                              |
|-------------|----------------|----------------------------------|
| 文件编辑      | 只写文件       | 写文件 + 自动 commit              |
| Git 操作     | 无             | `git_auto_commit()`              |
| Diff 注入    | 无             | tool_result 后追加 diff stat      |
| Agent loop  | 不变           | 不变                              |

## 试一试

```bash
python agents/s08_git_integration.py
```

推荐 prompt：

1. `Create a new file called config.py with a DEBUG constant`
2. `Edit config.py to set DEBUG = False`
3. `Run git log` — 应该看到 agent 的自动 commit
4. `Run git diff HEAD~1` — 查看最近一次 commit 的变更
