# s02: Tool Dispatch

> **Key insight**: Adding tools doesn't change the loop — just register to the dispatch map.

## The Problem

With only `bash`, everything goes through shell. `cat` truncation is unpredictable, `sed` breaks on special characters, and every bash call is an unconstrained attack surface. Dedicated tools (`read_file`, `write_file`) can enforce path sandboxing at the tool level.

## The Solution

```
+--------+      +-------+      +------------------+
|  User  | ---> |  LLM  | ---> | Tool Dispatch    |
| prompt |      |       |      | {                |
+--------+      +---+---+      |   bash: run_bash |
                    ^           |   read: run_read |
                    |           |   write: run_wr  |
                    +-----------+   edit: run_edit |
                    tool_result | }                |
                                +------------------+
```

The dispatch map is a dict: `{tool_name: handler_function}`. One lookup replaces any if/elif chain.

## How It Works

1. Each tool has a handler function. Path sandboxing prevents workspace escape.

```python
def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path

def run_read(path: str, limit: int = None) -> str:
    text = safe_path(path).read_text()
    lines = text.splitlines()
    if limit and limit < len(lines):
        lines = lines[:limit]
    return "\n".join(lines)[:50000]
```

2. Dispatch map maps tool names to handler functions.

```python
TOOL_HANDLERS = {
    "bash":       lambda **kw: run_bash(kw["command"]),
    "read_file":  lambda **kw: run_read(kw["path"], kw.get("limit")),
    "write_file": lambda **kw: run_write(kw["path"], kw["content"]),
    "edit_file":  lambda **kw: run_edit(kw["path"], kw["old_text"],
                                        kw["new_text"]),
}
```

3. Loop looks up handler by name. Loop body is identical to s01.

```python
for block in response.content:
    if block.type == "tool_use":
        handler = TOOL_HANDLERS.get(block.name)
        output = handler(**block.input) if handler \
            else f"Unknown tool: {block.name}"
        results.append({
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": output,
        })
```

Adding a tool = adding a handler + adding a schema. The loop never changes.

## What Changed from s01

| Component    | s01                 | s02                              |
|-------------|---------------------|----------------------------------|
| Tools       | 1 (bash only)       | 5 (bash, read, write, edit, find)|
| Dispatch    | Hardcoded bash call | `TOOL_HANDLERS` dict             |
| Path safety | None                | `safe_path()` sandbox            |
| Agent loop  | Unchanged           | Unchanged                        |

## Try It

```bash
python agents/s02_tool_dispatch.py
```

Recommended prompts:

1. `Read the file requirements.txt`
2. `Create a file called greet.py with a greet(name) function`
3. `Edit greet.py to add a docstring to the function`
4. `Read greet.py to verify the edit worked`
