"""CLI entry point for Agentic Coder."""

import argparse
import atexit
import os
import sys
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from ui.console import print_error, print_info

__version__ = "1.0.0"

# Load .env from: 1) CWD (project-specific) 2) ~/.agentic-coder/ (user global)
# Both use override=False so explicit env vars always take precedence
load_dotenv(Path.home() / ".agentic-coder" / ".env", override=False)
load_dotenv(Path.cwd() / ".env", override=False)


def parse_args():
    p = argparse.ArgumentParser(description="Agentic Coder - AI coding agent")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
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

    # Validate API key before proceeding
    if not os.getenv("ANTHROPIC_API_KEY"):
        print_error("ANTHROPIC_API_KEY is not set.")
        print_info(
            "Set it via one of:\n"
            "  1. Environment variable:  export ANTHROPIC_API_KEY=sk-ant-...\n"
            "  2. .env file in CWD:      echo ANTHROPIC_API_KEY=sk-ant-... > .env\n"
            "  3. Global config:         echo ANTHROPIC_API_KEY=sk-ant-... > ~/.agentic-coder/.env"
        )
        sys.exit(1)

    # Import here to ensure tool registration happens before engine uses them
    import tools.fs      # noqa: F401 - registers file tools
    import tools.shell   # noqa: F401 - registers shell tool
    import tools.git     # noqa: F401 - registers git_log tool
    import tools.agent_tools  # noqa: F401 - registers agent tools
    from core.commands import handle_input
    from core.engine import Engine
    from core.llm import AnthropicClient
    from core.prompts import build_system_prompt
    from core.session import load_session, most_recent_name
    from core.state import get_state, init_state
    from ui.console import console, print_info, print_session_history
    from ui.input import get_input

    init_state()

    llm = AnthropicClient(model=args.model)
    get_state().llm = llm

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

        try:
            engine.run(result)
        except anthropic.APIError as e:
            print_error(f"API error: {e}")
        except KeyboardInterrupt:
            print_info("\ninterrupted")
        _auto_save_session(engine)
        console.print()


if __name__ == "__main__":
    main()
