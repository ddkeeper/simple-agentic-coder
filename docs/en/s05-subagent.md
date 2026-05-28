# s05: Subagent

> **Key insight**: Break big tasks into small ones — each subtask gets a clean context, parent stays sharp.

## The Problem

The longer an agent works, the more bloated the messages array gets. Every file read, command output stays in context permanently. "What test framework does this project use?" might require reading 5 files, but the parent agent only needs one word: "pytest."

## The Solution

```
Parent agent                     Subagent
+------------------+             +------------------+
| messages=[...]   |             | messages=[]      | <-- fresh
|                  |  dispatch   |                  |
| tool: task       | ----------> | while tool_use:  |
|   prompt="..."   |             |   call tools     |
|                  |  summary    |   append results |
|   result = "..." | <---------- | return last text |
+------------------+             +------------------+

Parent context stays clean. Subagent context is discarded.
```

## How It Works

1. Parent agent has a `task` tool. Subagent gets all base tools *except* `task` (prevents recursive spawning).

```python
PARENT_TOOLS = CHILD_TOOLS + [
    {"name": "task",
     "description": "Spawn a subagent with fresh context.",
     "input_schema": {
         "type": "object",
         "properties": {"prompt": {"type": "string"}},
         "required": ["prompt"],
     }},
]
```

2. `task` handler creates a brand new messages array, calls the same agent_loop.

```python
def run_task(prompt: str) -> str:
    child_messages = [{"role": "user", "content": prompt}]
    agent_loop(child_messages, tools=CHILD_TOOLS)
    # Return only the last assistant text
    last = child_messages[-1]["content"]
    if isinstance(last, list):
        texts = [b.text for b in last if hasattr(b, "text")]
        return "\n".join(texts) if texts else "(no output)"
    return str(last)
```

3. Subagent context is discarded after return; parent gets only the summary.

## Key Constraints

- Subagent cannot spawn its own subagent (`task` tool not passed down)
- Subagent returns plain text summary, not full message history
- Subagent cannot see parent's messages — fully isolated

## What Changed from s04

| Component    | s04           | s05                                    |
|-------------|---------------|----------------------------------------|
| Tools       | 6             | 6 + task (parent) / 5 (child)          |
| Context model | Single messages | Parent-child separation, child discarded |
| Agent loop  | Unchanged     | Same function, different tools list    |

## Try It

```bash
python agents/s05_subagent.py
```

Recommended prompts:

1. `Analyze this project structure — what files exist and what do they do?`
2. `Find the test file and check what testing framework it uses`
3. `Create a utility module, then create tests for it — use subtasks`
