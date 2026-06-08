"""Agent tools: background tasks + orchestrator delegation.

Thin shells that validate parameters and delegate to core modules.
"""

from __future__ import annotations

from agentic_coder.tools.registry import tool


@tool("Run a shell command in the background. Returns a task_id for later status checking.")
def run_background(command: str) -> str:
    from agentic_coder.core.tasks import get_task_runner
    runner = get_task_runner()
    try:
        task_id = runner.start(command)
        return f"Background task started: {task_id}"
    except RuntimeError as e:
        return f"Error: {e}"


@tool("Check the status and output of a background task by task_id.")
def check_task_logs(task_id: str) -> str:
    from agentic_coder.core.tasks import get_task_runner
    runner = get_task_runner()
    result = runner.check(task_id)
    if "error" in result:
        return f"Error: {result['error']}"
    lines = [
        f"Task: {result['task_id']} ({result['status']})",
        f"Command: {result['command']}",
    ]
    if result["exit_code"] is not None:
        lines.append(f"Exit code: {result['exit_code']}")
    if result["stdout"]:
        lines.append(f"--- stdout ---\n{result['stdout']}")
    return "\n".join(lines)


@tool("Delegate a complex sub-task to a focused sub-agent. Returns a summary of the sub-agent's work.")
def delegate_task(task_description: str, tools: list[str] | None = None) -> str:
    from agentic_coder.core.orchestrator import run_sub_agent
    result = run_sub_agent(task_description, allowed_tools=tools)
    if len(result) > 4000:
        return result[:4000] + "\n...[Truncated]"
    return result
