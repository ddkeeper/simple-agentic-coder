# s01: Agent Loop

> **Key insight**: One loop + bash tool = one working agent.

## The Problem

Language models can reason about code but can't touch the real world — can't read files, run tests, or see errors. Without a loop, every tool call requires you to manually paste results back. *You* are the loop.

## The Solution

```
+--------+      +-------+      +---------+
|  User  | ---> |  LLM  | ---> |  Tool   |
| prompt |      |       |      | execute |
+--------+      +---+---+      +----+----+
                    ^                |
                    |   tool_result  |
                    +----------------+
                    (loop until stop_reason != "tool_use")
```

One exit condition controls the entire flow. The loop keeps running until the model stops calling tools.

## How It Works

1. User prompt becomes the first message.

```python
messages.append({"role": "user", "content": query})
```

2. Send messages and tool definitions to the LLM.

```python
response = client.messages.create(
    model=MODEL, system=SYSTEM, messages=messages,
    tools=TOOLS, max_tokens=8000,
)
```

3. Append assistant response. Check `stop_reason` — if no tool was called, done.

```python
messages.append({"role": "assistant", "content": response.content})
if response.stop_reason != "tool_use":
    return
```

4. Execute each tool call, collect results, append as user message. Go to step 2.

```python
results = []
for block in response.content:
    if block.type == "tool_use":
        output = run_bash(block.input["command"])
        results.append({
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": output,
        })
messages.append({"role": "user", "content": results})
```

Under 30 lines total — that's the entire Agent. The next 9 chapters all layer mechanisms onto this loop. The loop itself never changes.

## What Changed

| Component    | Before | After                       |
|-------------|--------|-----------------------------|
| Agent loop  | None   | `while True` + stop_reason  |
| Tools       | None   | `bash` (single tool)        |
| Messages    | None   | Accumulating message list   |
| Control flow| None   | `stop_reason != "tool_use"` |

## Try It

```bash
python agents/s01_agent_loop.py
```

Recommended prompts:

1. `Create a file called hello.py that prints "Hello, World!"`
2. `List all Python files in this directory`
3. `What is the current git branch?`
4. `Create a directory called test_output and write 3 files in it`
