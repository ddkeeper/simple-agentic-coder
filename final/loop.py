#!/usr/bin/env python3
"""Core agent loop — the heart of the system.

This loop never changes. All features (tools, permissions, compaction)
are layered around it, not inside it.
"""

import json

from anthropic import Anthropic

from .compaction import compact_messages, estimate_tokens
from .tools import TOOL_HANDLERS, TOOLS


def build_system_prompt(config: dict) -> str:
    return f"""You are a coding agent working in {config['cwd']}.

## Capabilities
- Read, write, edit files
- Run shell commands
- Find files by name pattern
- Manage task plans (todo)
- Spawn subagents for isolated research
- Run long commands in the background

## Rules
- Act, don't explain. Make changes directly.
- Use tools to verify your work (read after edit).
- Keep working until the task is fully complete.
- Never fabricate file contents — always read first.
- Update todos after each meaningful step.
"""


def agent_loop(
    messages: list,
    system: str = "",
    config: dict = None,
    tools: list = None,
    is_subagent: bool = False,
):
    client = Anthropic()
    config = config or {}
    tools = tools or TOOLS
    max_tokens = config.get("max_tokens", 8000)
    model = config.get("model", "claude-sonnet-4-20250514")

    rounds = 0
    while True:
        # Compact if messages are getting too long
        threshold = config.get("compact_threshold", 40_000)
        if not is_subagent and estimate_tokens(messages) > threshold:
            compact_messages(messages, config)

        response = client.messages.create(
            model=model,
            system=system,
            messages=messages,
            tools=tools,
            max_tokens=max_tokens,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            return

        results = []
        for block in response.content:
            if block.type == "tool_use":
                handler = TOOL_HANDLERS.get(block.name)
                if handler:
                    output = handler(**block.input, config=config)
                else:
                    output = f"Unknown tool: {block.name}"
                print(f"\033[33m> {block.name}\033[0m: {str(output)[:200]}")
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output,
                })
        messages.append({"role": "user", "content": results})
        rounds += 1
