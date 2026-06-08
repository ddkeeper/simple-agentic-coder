"""Terminal UI with rich.Console: static output + streaming Live rendering."""

from __future__ import annotations

import sys

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown

console = Console(file=sys.stdout)


def print_user(text: str) -> None:
    console.print(f"[bold cyan]>>[/] {text}")


def print_assistant(text: str) -> None:
    if text:
        console.print(text)


def print_tool(name: str, output: str, max_len: int = 200) -> None:
    preview = output[:max_len] + ("..." if len(output) > max_len else "")
    console.print(f"[dim]  > {name}:[/] {preview}")


def print_error(text: str) -> None:
    console.print(f"[bold red]Error:[/] {text}")


def print_info(text: str) -> None:
    console.print(f"[cyan]{text}[/]")


def print_compact(msg: str) -> None:
    console.print(f"[yellow]>> compact:[/] {msg}")


def stream_print(gen) -> str:
    """Consume a send_stream() generator and render with rich.Live.

    Args:
        gen: Generator yielding (StreamContext, StreamEvent) tuples.
             Caller already captured StreamContext from the first yield.

    Returns:
        The accumulated text string.
    """
    buffer = ""

    with Live(
        console=console,
        refresh_per_second=12,
        transient=False,
        vertical_overflow="ellipsis",
    ) as live:
        for _ctx, event in gen:
            if event.type == "text_delta":
                buffer += event.text
                if buffer.strip():
                    live.update(Markdown(buffer))
            elif event.type == "tool_start":
                live.update(Markdown(buffer) if buffer.strip() else "")
                console.print(f"[dim]  calling {event.tool_name}...[/]")
            elif event.type == "stream_end":
                break

    return buffer


def print_token_usage(usage: dict) -> None:
    """Print token usage in dim style after an LLM response."""
    in_tok = usage.get("input_tokens", 0)
    out_tok = usage.get("output_tokens", 0)
    console.print(f"[dim]  input: {in_tok:,} tokens | output: {out_tok:,} tokens[/]")


def print_session_history(messages: list) -> None:
    """Display conversation history of a resumed session."""
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content")
        if role == "user" and isinstance(content, str):
            console.print(f"[bold cyan]>>[/] {content}")
        elif role == "assistant" and isinstance(content, list):
            texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
            tool_names = [b.get("name", "") for b in content if isinstance(b, dict) and b.get("type") == "tool_use"]
            for t in texts:
                if t.strip():
                    console.print(t)
            for tn in tool_names:
                console.print(f"[dim]  called {tn}[/]")
