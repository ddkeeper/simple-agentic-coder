"""Minimal terminal UI with rich.Console for colored output."""

from __future__ import annotations

from rich.console import Console

console = Console()


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
    console.print(f"[dim]{text}[/]")


def print_compact(msg: str) -> None:
    console.print(f"[yellow]>> compact:[/] {msg}")
