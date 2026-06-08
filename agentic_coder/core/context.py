"""Context window management: microcompact + auto_compact.

microcompact: silently clears stale tool_result content from old messages.
auto_compact: uses LLM to summarize old messages when token count is too high.
"""

from __future__ import annotations

import json

from agentic_coder.core.llm import AnthropicClient
from agentic_coder.ui.console import print_compact


def estimate_tokens(messages: list) -> int:
    """Rough token estimate: ~4 chars per token."""
    try:
        text = json.dumps(messages, default=str)
    except Exception:
        text = str(messages)
    return len(text) // 4


def microcompact(messages: list, keep_turns: int = 3) -> int:
    """Clear stale tool_result content from messages older than keep_turns.

    Preserves read_file results (model may still reference them).
    Returns number of entries cleared.
    """
    cutoff = len(messages) - keep_turns * 2
    if cutoff <= 0:
        return 0

    cleared = 0
    for msg in messages[:cutoff]:
        if msg.get("role") != "user":
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_result":
                continue
            # Preserve read_file results
            tool_name = block.get("_tool_name", "")
            if tool_name == "read_file":
                continue
            original = block.get("content", "")
            if isinstance(original, str) and len(original) > 100:
                block["content"] = "[cleared by microcompact]"
                cleared += 1

    if cleared > 0:
        tokens_after = estimate_tokens(messages)
        print_compact(f"microcompact cleared {cleared} stale tool_result(s), ~{tokens_after} tokens remaining")
    return cleared


def auto_compact(
    messages: list,
    llm_client: AnthropicClient,
    threshold: int = 40000, # by deafult: 40000
    keep_recent: int = 6,
) -> bool:
    """Compact old messages into a summary when token count exceeds threshold.

    Replaces old messages in-place with a summary.
    Returns True if compaction was triggered.
    """
    tokens_before = estimate_tokens(messages)
    if tokens_before <= threshold:
        return False

    if len(messages) <= keep_recent + 2:
        return False

    if keep_recent == 0:
        old = messages[:]
        recent = []
    else:
        old = messages[:-keep_recent]
        recent = messages[-keep_recent:]

    print_compact(f"auto_compact triggered: ~{tokens_before} tokens > {threshold} threshold, summarizing {len(old)} old messages ...")

    # Build summary request
    old_text = json.dumps(old, default=str, ensure_ascii=False)
    if len(old_text) > 80000:
        old_text = old_text[:80000] + "\n... (truncated)"

    summary_prompt = [{
        "role": "user",
        "content": (
            "Summarize the following conversation in under 300 words. "
            "Preserve all key facts, file paths, decisions, and current task state.\n\n"
            f"{old_text}"
        ),
    }]

    try:
        response = llm_client.send(
            system="You are a concise summarizer.",
            messages=summary_prompt,
            max_tokens=600,
        )
        # Handle ThinkingBlock (MiMo) vs TextBlock (Claude)
        summary = ""
        for block in response.content:
            if hasattr(block, "text"):
                summary = block.text
                break
    except Exception:
        print_compact("auto_compact LLM call failed, keeping original messages")
        return False  # fail silently, keep original messages

    # Replace old messages with summary
    messages.clear()
    messages.append({"role": "user", "content": f"[Conversation summary]\n{summary}"})
    messages.extend(recent)

    tokens_after = estimate_tokens(messages)
    print_compact(f"auto_compact done: ~{tokens_before} -> ~{tokens_after} tokens, kept {keep_recent} recent messages")
    return True
