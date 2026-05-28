# s09: Background Tasks

> **核心洞察**: 耗时任务丢后台，主循环不阻塞——agent 可以同时做多件事。

## 问题

`bash` 工具执行测试套件可能要 2 分钟。在等待期间，agent 整个循环被阻塞，用户也无法交互。一个简单的 `pytest` 可能让整个 agent 停摆 120 秒。

## 解决方案

```
User: "Run the tests and fix any failures"

Agent calls bash(command="pytest", background=true)
  --> Returns immediately with task_id="task_1"

Agent can now:
  - Read other files
  - Write code
  - Respond to user

Later: Agent calls task_output(task_id="task_1")
  --> Gets test results
  --> Fixes failures
```

## 工作原理

1. bash 工具增加 `background` 参数。

```python
TASKS = {}  # {task_id: {"proc": Popen, "status": "running"}}

def run_bash(command, background=False):
    if not background:
        return execute_sync(command)

    task_id = f"task_{len(TASKS) + 1}"
    proc = subprocess.Popen(
        command, shell=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, cwd=WORKDIR,
    )
    TASKS[task_id] = {"proc": proc, "status": "running"}
    return f"Background task started: {task_id}"
```

2. `task_output` 工具查询后台任务状态。

```python
def run_task_output(task_id):
    task = TASKS.get(task_id)
    if not task:
        return f"Error: Unknown task {task_id}"
    if task["proc"].poll() is None:
        return f"Task {task_id} still running..."
    stdout, stderr = task["proc"].communicate()
    task["status"] = "done"
    return f"Exit code: {task['proc'].returncode}\n{stdout}\n{stderr}"
```

3. bash schema 增加 `background` 字段。

```python
{
    "name": "bash",
    "input_schema": {
        "type": "object",
        "properties": {
            "command":  {"type": "string"},
            "background": {"type": "boolean", "default": False},
        },
        "required": ["command"],
    },
}
```

## 与 Subagent 的区别

| | Background Task | Subagent |
|---|---|---|
| 上下文 | 共享父上下文 | 独立上下文 |
| 适用场景 | 耗时 shell 命令 | 需要多轮推理的子任务 |
| 结果返回 | 轮询 `task_output` | 立即返回摘要 |
| 典型用例 | `npm test`、`docker build` | "分析这个模块的结构" |

## 相对 s08 的变更

| 组件         | s08            | s09                              |
|-------------|----------------|----------------------------------|
| bash 工具    | 同步执行        | + `background` 参数              |
| 新增工具     | 无              | `task_output`                    |
| 新增状态     | 无              | `TASKS` 字典                     |
| Agent loop  | 不变            | 不变                              |

## 试一试

```bash
python agents/s09_background.py
```

推荐 prompt：

1. `Run `sleep 5 && echo "done"` in the background`
2. `Now read the file hello.py while we wait`
3. `Check the status of the background task`
4. `Run `pytest` in the background and let me know when it's done`
