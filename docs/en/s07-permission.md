# s07: Permission System

> **Key insight**: The more autonomous the agent, the more it needs constraints — permissions draw the line between capability and safety.

## The Problem

With full tool access, the agent can delete files, execute arbitrary commands, rewrite critical configs. Fully trusting the model is dangerous, but asking the user every step breaks flow.

## The Solution

Tools split into three tiers:

| Tier  | Behavior          | Examples                                  |
|-------|-------------------|-------------------------------------------|
| `auto` | Silent execution  | `read_file`, `find_files`                 |
| `ask`  | Ask before exec   | `write_file`, `edit_file`, `bash` (non-readonly) |
| `deny` | Block immediately | `bash` containing `rm -rf`                |

```python
PERMISSIONS = {
    "read_file":  "auto",
    "find_files": "auto",
    "write_file": "ask",
    "edit_file":  "ask",
    "bash":       "ask",  # can further judge in handler
}
```

## How It Works

1. Check permissions before dispatch.

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

2. Bash handler does fine-grained judgment: readonly commands (`ls`, `cat`) auto-pass, write commands ask.

```python
READONLY_PREFIXES = ["ls", "cat", "head", "tail", "pwd", "git status", "git log"]

def run_bash(command, io):
    if any(command.strip().startswith(p) for p in READONLY_PREFIXES):
        return execute(command)  # auto
    if not io.confirm(f"$ {command}"):
        return "Error: User denied"
    return execute(command)
```

3. `--yes` mode: when CLI starts with `--yes`, all `ask` downgrades to `auto` — good for CI.

```python
if args.yes:
    PERMISSIONS = {k: "auto" for k in PERMISSIONS}
```

## Confirmation UX

Permission prompts should be instant and clear. Show tool name and key params in one line:

```
$ bash: rm temp.txt   [y/n/!]
```

- `y`: Allow this time
- `n`: Deny this time
- `!`: Allow this tool for the entire session

## What Changed from s06

| Component    | s06           | s07                              |
|-------------|---------------|----------------------------------|
| Tool execution | Direct exec | Permission check layer          |
| New component | None         | `PERMISSIONS` dict + confirm    |
| Agent loop  | Unchanged     | + permission check layer        |

## Try It

```bash
python agents/s07_permission.py
```

Recommended prompts (observe permission behavior):

1. `Read the file hello.py` — should auto-execute
2. `Write "hello" to test.txt` — should ask
3. `Run ls -la` — should auto-execute
4. `Run rm test.txt` — should ask
