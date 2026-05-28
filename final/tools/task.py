#!/usr/bin/env python3
"""Subagent tool — spawn an isolated agent_loop with fresh context."""

from ..loop import agent_loop
from . import CHILD_TOOLS


def run_task(prompt: str, system: str = "", config: dict = None) -> str:
    """Spawn a subagent with a fresh messages array."""
    child_messages = [{"role": "user", "content": prompt}]
    agent_loop(
        messages=child_messages,
        system=system,
        config=config,
        tools=CHILD_TOOLS,
        is_subagent=True,
    )
    # Return only the last assistant text
    last = child_messages[-1]["content"]
    if isinstance(last, list):
        texts = [b.text for b in last if hasattr(b, "text")]
        return "\n".join(texts) if texts else "(no output)"
    return str(last)
