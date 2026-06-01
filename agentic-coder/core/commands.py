"""Slash command registration and dispatch.

Commands are local actions that don't consume API tokens.
They run before engine.run() in the input loop.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from core.engine import Engine

COMMANDS: dict[str, Callable] = {}


def register_command(name: str, handler: Callable | None = None) -> Callable:
    """Register a /name command. Can be used as decorator or direct call.

    @register_command("clear")
    def cmd_clear(engine, arg): ...

    register_command("clear", my_handler)
    """
    if handler is not None:
        COMMANDS[name] = handler
        return handler

    def decorator(fn: Callable) -> Callable:
        COMMANDS[name] = fn
        return fn
    return decorator


def handle_input(text: str, engine: Engine) -> str | None:
    """Check if input is a slash command.

    Returns None if it was a command (already handled).
    Returns the original text unchanged for engine.run().
    """
    stripped = text.strip()
    if not stripped.startswith("/"):
        return text

    # /command [args...]
    parts = stripped.split(maxsplit=1)
    cmd = parts[0][1:]  # remove leading /
    arg = parts[1] if len(parts) > 1 else ""

    handler = COMMANDS.get(cmd)
    if handler is None:
        from ui.console import print_error
        print_error(f"Unknown command: /{cmd}. Type /help for available commands.")
        return None

    handler(engine, arg)
    return None


def list_commands() -> list[str]:
    """Return sorted list of registered command names."""
    return sorted(COMMANDS.keys())


# ── Built-in commands ──────────────────────────────────────────────────

@register_command("clear")
def cmd_clear(engine: Engine, arg: str) -> None:
    """Clear conversation history."""
    engine.messages.clear()
    from ui.console import print_info
    print_info("conversation cleared")


@register_command("compact")
def cmd_compact(engine: Engine, arg: str) -> None:
    """Force context compaction."""
    from core.context import auto_compact, estimate_tokens
    from ui.console import print_compact

    tokens = estimate_tokens(engine.messages)
    if len(engine.messages) <= 2:
        print_compact(f"nothing to compact (~{tokens} tokens, {len(engine.messages)} messages)")
        return

    triggered = auto_compact(
        engine.messages, engine.llm,
        threshold=0,
        keep_recent=0,  # summarize everything when user explicitly requests
    )
    if not triggered:
        print_compact(f"nothing to compact (~{tokens} tokens, {len(engine.messages)} messages)")


@register_command("exit")
def cmd_exit(engine: Engine, arg: str) -> None:
    """Exit the program."""
    raise SystemExit


@register_command("help")
def cmd_help(engine: Engine, arg: str) -> None:
    """List available commands."""
    from ui.console import console
    console.print("\n[bold]Available commands:[/]")
    for name in list_commands():
        handler = COMMANDS[name]
        doc = (handler.__doc__ or "").strip().split("\n")[0]
        console.print(f"  [cyan]/{name}[/]  {doc}")
    console.print()


@register_command("resume")
def cmd_resume(engine: Engine, arg: str) -> None:
    """Resume a saved session. Auto-saves current session first. Usage: /resume [name]"""
    import os as _os
    import time as _time
    from core.session import load_session, most_recent_name, save_session
    from ui.console import console, print_info, print_session_history

    # /resume without name → most recent session
    raw = arg.strip()
    name = raw if raw else (most_recent_name() or "last")

    # Auto-save current session before switching (use its own name, or timestamp if new)
    if engine.messages:
        save_name = getattr(engine, '_session_name', None) or _time.strftime("session_%Y%m%d_%H%M%S")
        save_session(engine, save_name)

    session = load_session(name)
    if session:
        engine.messages = session["messages"]
        engine._session_name = name
        # Clear screen and show new session
        _os.system('cls' if _os.name == 'nt' else 'clear')
        console.print(f"\n[bold cyan]Agentic Coder[/] ({engine.llm.model})")
        console.print("[dim]Type 'q' or 'exit' to quit. /help for commands. Alt+Enter for newlines.[/]\n")
        print_info(f"session resumed: {name}, {session['message_count']} messages")
        print_session_history(engine.messages)
    else:
        print_info(f"session '{name}' not found")


@register_command("sessions")
def cmd_sessions(engine: Engine, arg: str) -> None:
    """List saved sessions."""
    from core.session import list_sessions
    from ui.console import console
    sessions = list_sessions()
    if not sessions:
        console.print("[dim]  No saved sessions.[/]")
        return
    console.print("\n[bold]Saved sessions:[/]")
    for s in sessions:
        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(s["timestamp"]))
        console.print(
            f"  [cyan]{s['name']}[/]  "
            f"{s['message_count']} messages  "
            f"{s['model']}  "
            f"[dim]{ts}[/]"
        )
    console.print(f"\n[dim]  Use /resume {sessions[0]['name']} to restore.[/]\n")
