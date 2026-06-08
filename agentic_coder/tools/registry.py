"""Tool registry with automatic Anthropic schema generation.

Uses inspect + Pydantic to dynamically generate JSON Schema from
Python function signatures and type annotations.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import create_model

TOOL_REGISTRY: dict[str, ToolEntry] = {}


@dataclass
class ToolEntry:
    name: str
    description: str
    func: Callable
    schema: dict
    dangerous: bool = False


def _build_schema(func: Callable, description: str) -> dict:
    """Build an Anthropic-compatible tool schema from a function signature."""
    sig = inspect.signature(func)
    fields = {}
    required_params = []

    for name, param in sig.parameters.items():
        annotation = param.annotation if param.annotation != inspect.Parameter.empty else str
        default = param.default if param.default != inspect.Parameter.empty else ...
        fields[name] = (annotation, default)
        if default is ...:
            required_params.append(name)

    model = create_model(f"{func.__name__}_params", **fields)
    json_schema = model.model_json_schema()

    return {
        "name": func.__name__,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": json_schema.get("properties", {}),
            "required": required_params,
        },
    }


def tool(description: str = "", dangerous: bool = False):
    """Decorator to register a function as an agent tool.

    Usage:
        @tool("Read file contents")
        def read_file(path: str, limit: int | None = None) -> str:
            ...
    """
    def decorator(func: Callable) -> Callable:
        schema = _build_schema(func, description)
        entry = ToolEntry(
            name=func.__name__,
            description=description,
            func=func,
            schema=schema,
            dangerous=dangerous,
        )
        TOOL_REGISTRY[func.__name__] = entry
        return func
    return decorator


def get_anthropic_tools() -> list[dict]:
    """Export all registered tools as an Anthropic-compatible tools list."""
    return [entry.schema for entry in TOOL_REGISTRY.values()]


def execute_tool(name: str, tool_input: dict) -> str:
    """Execute a registered tool by name with the given input dict."""
    entry = TOOL_REGISTRY.get(name)
    if entry is None:
        return f"Error: Unknown tool '{name}'"
    try:
        result = entry.func(**tool_input)
        return str(result) if result is not None else "(no output)"
    except Exception as e:
        return f"Error ({name}): {type(e).__name__}: {e}"


def is_dangerous(name: str) -> bool:
    """Check if a tool is marked as dangerous."""
    entry = TOOL_REGISTRY.get(name)
    return entry.dangerous if entry else False
