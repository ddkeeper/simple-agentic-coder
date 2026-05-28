# s04: TodoWrite

> **Key insight**: An agent without a plan drifts — list steps first, double the completion rate.

## The Problem

During multi-step tasks, the model loses progress: repeats completed work, skips steps, goes off track. The longer the conversation, the worse it gets. Tool results fill the context, diluting system prompt influence. A 10-step refactor may start improvising after step 3 because steps 4-10 were pushed out of attention.

## The Solution

```
+--------+      +-------+      +---------+
|  User  | ---> |  LLM  | ---> | Tools   |
| prompt |      |       |      | + todo  |
+--------+      +---+---+      +----+----+
                    ^                |
                    |   tool_result  |
                    +----------------+
                          |
              +-----------+-----------+
              | TodoManager state     |
              | [ ] task A            |
              | [>] task B <- doing   |
              | [x] task C            |
              +-----------------------+
                          |
              if rounds_since_todo >= 3:
                inject <reminder> into tool_result
```

## How It Works

1. TodoManager stores stateful items. Only one `in_progress` at a time.

```python
class TodoManager:
    def update(self, items: list) -> str:
        validated, in_progress_count = [], 0
        for item in items:
            status = item.get("status", "pending")
            if status == "in_progress":
                in_progress_count += 1
            validated.append({
                "id": item["id"],
                "text": item["text"],
                "status": status,
            })
        if in_progress_count > 1:
            raise ValueError("Only one task can be in_progress")
        self.items = validated
        return self.render()
```

2. `todo` tool joins the dispatch map like any other tool.

```python
TOOL_HANDLERS = {
    # ...base tools...
    "todo": lambda **kw: TODO.update(kw["items"]),
}
```

3. Nag reminder: inject reminder when model goes 3+ rounds without calling `todo`.

```python
if rounds_since_todo >= 3 and messages:
    last = messages[-1]
    if last["role"] == "user" and isinstance(last.get("content"), list):
        last["content"].insert(0, {
            "type": "text",
            "text": "<reminder>Update your todos.</reminder>",
        })
```

"Only one in_progress at a time" forces sequential focus. Nag reminder creates accountability — don't update your plan, the system nags you.

## Why Not a Simple Checklist

TodoWrite differs fundamentally from checklist text:
- **State management**: `pending` / `in_progress` / `completed`, enforced single focus
- **Machine-readable**: Agent can call programmatically, not parse its own text
- **Active reminder**: Injects when agent forgets to update, not passive

## What Changed from s03

| Component    | s03           | s04                                |
|-------------|---------------|------------------------------------|
| Tools       | 5             | 6 (+todo)                          |
| Planning    | None          | Stateful TodoManager               |
| Nag inject  | None          | `<reminder>` after 3 rounds        |
| Agent loop  | Simple dispatch | + rounds_since_todo counter       |

## Try It

```bash
python agents/s04_todo_write.py
```

Recommended prompts:

1. `Refactor the file hello.py: add type hints, docstrings, and a main guard`
2. `Create a Python package with __init__.py, utils.py, and tests/test_utils.py`
3. `Review all Python files and fix any style issues`
