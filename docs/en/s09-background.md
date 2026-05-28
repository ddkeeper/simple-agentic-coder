# s09: Background Tasks

> **Key insight**: Throw long-running tasks to the background — main loop stays responsive, agent can multitask.

## The Problem

`bash` tool running a test suite might take 2 minutes. While waiting, the entire agent loop is blocked — user can't interact. A simple `pytest` can freeze the agent for 120 seconds.

## The Solution

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

## How It Works

1. Bash tool adds `background` parameter.

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

2. `task_output` tool queries background task status.

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

3. Bash schema adds `background` field.

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

## Background Task vs Subagent

| | Background Task | Subagent |
|---|---|---|
| Context | Shares parent context | Isolated context |
| Use case | Long shell commands | Multi-step reasoning subtasks |
| Result return | Poll via `task_output` | Immediate summary |
| Examples | `npm test`, `docker build` | "Analyze this module's structure" |

## What Changed from s08

| Component    | s08           | s09                                |
|-------------|---------------|------------------------------------|
| Bash tool   | Sync execution | + `background` parameter          |
| New tool    | None           | `task_output`                     |
| New state   | None           | `TASKS` dict                      |
| Agent loop  | Unchanged      | Unchanged                          |

## Try It

```bash
python agents/s09_background.py
```

Recommended prompts:

1. `Run `sleep 5 && echo "done"` in the background`
2. `Now read the file hello.py while we wait`
3. `Check the status of the background task`
4. `Run `pytest` in the background and let me know when it's done`
