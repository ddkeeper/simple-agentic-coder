"""Pydantic data models for internal message passing."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolCallRequest(BaseModel):
    """Represents a tool call request from the LLM."""

    tool_name: str
    tool_input: dict[str, Any]
    tool_use_id: str


class ToolResult(BaseModel):
    """Represents the result of executing a tool."""

    tool_use_id: str
    content: str
    is_error: bool = False


class TextBlock(BaseModel):
    """A plain text block in a message."""

    type: Literal["text"] = "text"
    text: str


class AgentMessage(BaseModel):
    """A single message in the conversation history.

    content can be:
    - str (simple text)
    - list of TextBlock | ToolCallRequest | ToolResult
    """

    role: Literal["user", "assistant"]
    content: str | list[TextBlock | ToolCallRequest | ToolResult]


class AgentConfig(BaseModel):
    """Runtime configuration for the agent."""

    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 8000
    auto_approve: bool = False
    cwd: str = ""
    platform: str = ""
    date: str = ""
    git_branch: str = "unknown"
    file_tree: str = ""
    compact_threshold: int = 40000
    keep_recent: int = 6
