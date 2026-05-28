#!/usr/bin/env python3
"""Context compaction — compress old messages when context grows too large."""

import json

from anthropic import Anthropic


def estimate_tokens(messages: list) -> int:
    """Rough token estimate: ~4 chars per token."""
    try:
        text = json.dumps(messages, default=str)
    except Exception:
        text = str(messages)
    return len(text) // 4


def compact_messages(messages: list, config: dict) -> None:
    """Compact messages in-place by summarizing old ones.

    Keeps the system prompt and recent messages intact.
    Replaces old messages with a summary.
    """
    keep_recent = config.get("keep_recent", 6)
    model = config.get("model", "claude-sonnet-4-20250514")

    if len(messages) <= keep_recent + 2:
        return  # not enough to compact

    old = messages[:-keep_recent]
    recent = messages[-keep_recent:]

    # Build summary request
    old_text = json.dumps(old, default=str, ensure_ascii=False)
    summary_prompt = [{
        "role": "user",
        "content": (
            "Summarize the following conversation in under 300 words. "
            "Preserve all key facts, file paths, and decisions.\n\n"
            f"{old_text[:80000]}"
        ),
    }]

    client = Anthropic()
    try:
        response = client.messages.create(
            model=model, messages=summary_prompt, max_tokens=600,
        )
        summary = response.content[0].text
    except Exception:
        return  # fail silently, keep original messages

    # Replace old messages with summary
    compacted = [{"role": "user", "content": f"[Conversation summary]\n{summary}"}]
    messages.clear()
    messages.extend(compacted + recent)

    print(f"\033[90m[compacted {len(old)} messages into summary]\033[0m")
