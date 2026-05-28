#!/usr/bin/env python3
"""TodoManager — stateful task plan with enforced single focus."""

TODO_STATE = {"items": [], "rounds_since_update": 0}


def run_todo(items: list) -> str:
    validated = []
    in_progress_count = 0

    for item in items:
        status = item.get("status", "pending")
        if status == "in_progress":
            in_progress_count += 1
        validated.append({
            "id": item["id"],
            "text": item["text"],
            "status": status,
        })

    if in_progress_count > 1:
        return "Error: Only one task can be in_progress at a time"

    TODO_STATE["items"] = validated
    TODO_STATE["rounds_since_update"] = 0
    return _render(validated)


def _render(items: list) -> str:
    symbols = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]"}
    lines = []
    for item in items:
        sym = symbols.get(item["status"], "[ ]")
        lines.append(f"{sym} {item['id']}: {item['text']}")
    return "\n".join(lines)


def get_todo_nag() -> str | None:
    """Return a nag reminder if todo hasn't been updated in 3+ rounds."""
    TODO_STATE["rounds_since_update"] += 1
    if TODO_STATE["rounds_since_update"] >= 3 and TODO_STATE["items"]:
        return "<reminder>Update your todos — you haven't called todo in a while.</reminder>"
    return None
