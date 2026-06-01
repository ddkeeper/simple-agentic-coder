"""Session persistence: save/load conversation history as JSON."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.engine import Engine

SESSION_DIR = Path.home() / ".agentic-coder" / "sessions"


def _ensure_dir() -> None:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)


def _serialize_block(block) -> dict:
    """Convert an Anthropic SDK content block (or plain dict) to a plain dict."""
    if isinstance(block, dict):
        return block

    block_type = getattr(block, "type", None)

    if block_type == "text":
        return {"type": "text", "text": block.text}
    if block_type == "thinking":
        return {"type": "thinking", "thinking": block.thinking}
    if block_type == "tool_use":
        return {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
    if block_type == "tool_result":
        return {"type": "tool_result", "tool_use_id": block.tool_use_id,
                "content": block.content}

    # Fallback: try to extract common attributes
    result = {"type": block_type or "unknown"}
    for attr in ("text", "thinking", "id", "name", "input", "content", "tool_use_id"):
        if hasattr(block, attr):
            result[attr] = getattr(block, attr)
    return result


def _serialize_messages(messages: list) -> list:
    """Convert all messages to plain dicts suitable for JSON serialization."""
    serialized = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content")

        if isinstance(content, list):
            content = [_serialize_block(b) for b in content]

        serialized.append({"role": role, "content": content})
    return serialized


def save_session(engine: Engine, name: str = "last") -> Path:
    """Serialize engine.messages to a JSON file.

    File: sessions/{name}.json
    Content: {messages, model, timestamp, message_count}
    """
    _ensure_dir()
    path = SESSION_DIR / f"{name}.json"
    data = {
        "messages": _serialize_messages(engine.messages),
        "model": engine.llm.model,
        "timestamp": time.time(),
        "message_count": len(engine.messages),
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_session(name: str = "last") -> dict | None:
    """Load a session by name. Returns {messages, model, timestamp} or None."""
    path = SESSION_DIR / f"{name}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data.get("messages"), list):
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def load_most_recent() -> dict | None:
    """Load the most recently saved session. Returns {messages, model, ...} or None."""
    sessions = list_sessions()
    if not sessions:
        return None
    return load_session(sessions[0]["name"])


def most_recent_name() -> str | None:
    """Return the name of the most recently saved session, or None."""
    sessions = list_sessions()
    return sessions[0]["name"] if sessions else None


def list_sessions() -> list[dict]:
    """List all saved sessions, newest first.

    Returns list of {name, model, timestamp, message_count}.
    """
    _ensure_dir()
    sessions = []
    for path in SESSION_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            sessions.append({
                "name": path.stem,
                "model": data.get("model", "?"),
                "timestamp": data.get("timestamp", 0),
                "message_count": data.get("message_count", 0),
            })
        except (json.JSONDecodeError, OSError):
            continue
    sessions.sort(key=lambda s: s["timestamp"], reverse=True)
    return sessions
