# s03: System Prompt

> **Key insight**: A good system prompt is the agent's soul — it defines behavioral boundaries.

## The Problem

The s02 agent has tools but uncontrollable behavior: may output verbose explanations, forget the working directory, ignore coding style. Without a good prompt, strong capabilities go unused.

## The Solution

System prompt is injected every round as role configuration, defining who the agent is, what it can do, and how it should act.

```python
SYSTEM = """You are a coding agent working in {cwd}.

## Capabilities
- Read, write, edit files
- Run shell commands
- Find files by name pattern

## Rules
- Act, don't explain. Make changes directly.
- Use tools to verify your work (read after edit).
- Keep working until the task is fully complete.
- Never fabricate file contents — always read first.
"""
```

## How It Works

1. Dynamically inject context (working directory, OS, date).

```python
system = SYSTEM.format(
    cwd=os.getcwd(),
    platform=platform.system(),
    date=datetime.now().strftime("%Y-%m-%d"),
)
```

2. Prompt layers: Role > Rules > Context > Output format.

```python
SYSTEM = """
{role}              # Who you are
{rules}             # How you should act
{context}           # Current environment info
{output_format}     # Output format requirements
"""
```

3. Keep prompt concise. Every rule added must be validated for effectiveness — ineffective rules dilute attention from effective ones.

## Why English Prompts

Default English prompts because:
- Mainstream LLMs have stronger English instruction following
- English tokens are more efficient (same meaning, fewer tokens)
- Mixed Chinese/English in code contexts causes unstable output

Control user-side language when Chinese interaction is needed; keep prompts in English.

## What Changed from s02

| Component    | s02           | s03                               |
|-------------|---------------|-----------------------------------|
| System prompt | Single-line string | Layered template + dynamic context |
| Agent loop   | Unchanged     | Unchanged                         |

## Try It

```bash
python agents/s03_system_prompt.py
```

Recommended prompts:

1. `Create a Python calculator module with add, subtract, multiply, divide`
2. `Look at all Python files here and tell me the coding style`
3. `Refactor hello.py: add type hints and a proper main guard`
