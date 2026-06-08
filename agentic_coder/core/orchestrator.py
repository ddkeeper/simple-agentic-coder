"""Orchestrator: sub-agent delegation with isolated context."""

from __future__ import annotations

import time

from agentic_coder.core.context import auto_compact, microcompact
from agentic_coder.core.llm import AnthropicClient
from agentic_coder.tools.registry import execute_tool, get_anthropic_tools

MAX_ITERATIONS = 30
TIMEOUT_SECONDS = 300
DEFAULT_TOOLS = [
    "read_file", "list_files", "glob_search", "grep_search", "run_command",
]


def _build_child_prompt(task_description: str) -> str:
    return (
        f"You are a focused sub-agent. Your ONLY goal is:\n\n"
        f"{task_description}\n\n"
        f"Do not explore beyond this scope. "
        f"Complete the task and return a concise summary of what you did and the result."
    )


def _filter_tools(allowed: list[str]) -> list[dict]:
    all_tools = get_anthropic_tools()
    return [t for t in all_tools if t["name"] in allowed]


def run_sub_agent(
    task_description: str,
    llm: AnthropicClient | None = None,
    allowed_tools: list[str] | None = None,
) -> str:
    if allowed_tools is None:
        allowed_tools = DEFAULT_TOOLS
    if llm is None:
        from agentic_coder.core.state import get_state
        llm = get_state().llm

    prompt = _build_child_prompt(task_description)
    tools = _filter_tools(allowed_tools)
    messages: list[dict] = [{"role": "user", "content": task_description}]
    start = time.time()
    iterations = 0

    try:
        while iterations < MAX_ITERATIONS:
            if time.time() - start > TIMEOUT_SECONDS:
                return f"[Task Failed] Timeout after {TIMEOUT_SECONDS}s."

            microcompact(messages)
            auto_compact(messages, llm)

            response = llm.send(
                system=prompt,
                messages=messages,
                tools=tools,
                max_tokens=8000,
            )
            messages.append({"role": "assistant", "content": response.content})
            iterations += 1

            if response.stop_reason != "tool_use":
                text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        text += block.text
                return text or "[Task Completed] No text output."

            tool_results = []
            for block in response.content:
                if hasattr(block, "type") and block.type == "tool_use":
                    output = execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": output,
                    })
            if tool_results:
                messages.append({"role": "user", "content": tool_results})

        return f"[Task Failed] Max iterations ({MAX_ITERATIONS}) reached."

    except KeyboardInterrupt:
        return "[Task Interrupted] User cancelled the sub-agent."
    except Exception as e:
        return f"[Task Failed] {type(e).__name__}: {e}"
