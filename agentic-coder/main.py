"""CLI entry point for Agentic Coder."""

import argparse
import atexit
import os
import time
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the same directory as this script
_SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(_SCRIPT_DIR / ".env", override=True)


def parse_args():
    p = argparse.ArgumentParser(description="Agentic Coder - AI coding agent")
    p.add_argument("--model", default=os.getenv("MODEL_ID", "claude-sonnet-4-20250514"))
    p.add_argument("--yes", action="store_true", help="Auto-approve all tool calls")
    p.add_argument(
        "--resume", nargs="?", const="*recent*", default=None,
        help="Resume a saved session (default: most recent). Use /sessions to list available sessions.",
    )
    return p.parse_args()


def _auto_save_session(engine) -> None:
    """Save session to disk. Called after each response and on exit."""
    from core.session import save_session
    if engine.messages:
        name = getattr(engine, '_session_name', None) or time.strftime("session_%Y%m%d_%H%M%S")
        save_session(engine, name)
        if engine._session_name is None:
            engine._session_name = name


def main():
    args = parse_args()

    # Import here to ensure tool registration happens before engine uses them
    import tools.fs      # noqa: F401 - registers file tools
    import tools.shell   # noqa: F401 - registers shell tool
    import tools.git     # noqa: F401 - registers git_log tool
    from core.commands import handle_input
    from core.engine import Engine
    from core.llm import AnthropicClient
    from core.prompts import build_system_prompt
    from core.session import load_session, most_recent_name
    from ui.console import console, print_info, print_session_history
    from ui.input import get_input

    llm = AnthropicClient(model=args.model)
    engine = Engine(
        llm_client=llm,
        system_prompt=build_system_prompt(),
        auto_approve=args.yes,
    )
    engine._session_name = None

    # Banner (always shown first)
    console.print(f"\n[bold cyan]Agentic Coder[/] ({args.model})")
    console.print("[dim]Type 'q' or 'exit' to quit. /help for commands. Alt+Enter for newlines.[/]\n")

    # Resume session if requested
    if args.resume is not None:
        # --resume without value → most recent session
        name = (most_recent_name() or "last") if args.resume == "*recent*" else args.resume
        session = load_session(name)
        if session:
            engine.messages = session["messages"]
            engine._session_name = name
            msg_count = session["message_count"]
            print_info(f"session resumed: {name}, {msg_count} messages")
            print_session_history(engine.messages)
        else:
            print_info(f"session '{name}' not found, starting fresh")

    # Safety net: save on exit (covers edge cases like Ctrl+C in input())
    atexit.register(lambda: _auto_save_session(engine))

    while True:
        query = get_input()
        if query is None:
            break
        if query.strip().lower() in ("q", "exit"):
            break
        if not query.strip():
            continue

        # Slash command interception
        result = handle_input(query, engine)
        if result is None:
            console.print()
            continue

        engine.run(result)
        _auto_save_session(engine)
        console.print()


if __name__ == "__main__":
    main()
