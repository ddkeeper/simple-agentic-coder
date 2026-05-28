# s07: Permission System

> **核心洞察**: agent 越自主，越需要约束——权限系统在"能力"和"安全"之间画线。

## 问题

有了完整工具后，agent 可以删除文件、执行任意命令、改写重要配置。完全信任模型是危险的，但每步都问用户又会打断流程。

## 解决方案

工具分为三级：

| 级别 | 行为 | 示例 |
|-----|------|------|
| `auto` | 静默执行 | `read_file`, `find_files` |
| `ask` | 执行前询问用户 | `write_file`, `edit_file`, `bash`（非只读）|
| `deny` | 直接拒绝 | `bash` 包含 `rm -rf` |

```python
PERMISSIONS = {
    "read_file":  "auto",
    "find_files": "auto",
    "write_file": "ask",
    "edit_file":  "ask",
    "bash":       "ask",  # 可在 handler 里进一步判断
}
```

## 工作原理

1. dispatch 前检查权限。

```python
def execute_tool(block, io):
    level = PERMISSIONS.get(block.name, "ask")

    if level == "deny":
        return f"Error: {block.name} is not allowed"

    if level == "ask":
        if not io.confirm(f"Run {block.name}? {block.input}"):
            return "Error: User denied permission"

    handler = TOOL_HANDLERS[block.name]
    return handler(**block.input)
```

2. bash 工具内细粒度判断：只读命令（ls、cat）自动通过，写命令询问。

```python
READONLY_PREFIXES = ["ls", "cat", "head", "tail", "pwd", "git status", "git log"]

def run_bash(command, io):
    if any(command.strip().startswith(p) for p in READONLY_PREFIXES):
        return execute(command)  # auto
    if not io.confirm(f"$ {command}"):
        return "Error: User denied"
    return execute(command)
```

3. `--yes` 模式：CLI 启动时加 `--yes`，所有 `ask` 降级为 `auto`，适合 CI 环境。

```python
if args.yes:
    PERMISSIONS = {k: "auto" for k in PERMISSIONS}
```

## 用户确认的交互设计

权限确认需要即时、清晰。用一行显示工具名和关键参数：

```
$ bash: rm temp.txt   [y/n/!]
```

- `y`: 本次允许
- `n`: 本次拒绝
- `!`: 本次会话内对该工具全部允许

## 相对 s06 的变更

| 组件         | s06            | s07                           |
|-------------|----------------|-------------------------------|
| 工具执行      | 直接执行       | 经过 permission check          |
| 新增组件      | 无             | `PERMISSIONS` 字典 + confirm   |
| Agent loop  | 不变           | + 权限检查层                    |

## 试一试

```bash
python agents/s07_permission.py
```

推荐 prompt（观察权限确认行为）：

1. `Read the file hello.py` — 应该自动执行
2. `Write "hello" to test.txt` — 应该询问
3. `Run ls -la` — 应该自动执行
4. `Run rm test.txt` — 应该询问
