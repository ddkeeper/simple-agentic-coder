"""CLI entry point for Agentic Coder."""

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the same directory as this script
_SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(_SCRIPT_DIR / ".env", override=True)


def parse_args():
    p = argparse.ArgumentParser(description="Agentic Coder - AI coding agent")
    p.add_argument("--model", default=os.getenv("MODEL_ID", "claude-sonnet-4-20250514"))
    p.add_argument("--yes", action="store_true", help="Auto-approve all tool calls")
    return p.parse_args()


def main():
    args = parse_args()

    # Import here to ensure tool registration happens before engine uses them
    import tools.fs      # noqa: F401 - registers file tools
    import tools.shell   # noqa: F401 - registers shell tool
    import tools.git     # noqa: F401 - registers git_log tool
    from core.engine import Engine
    from core.llm import AnthropicClient
    from core.prompts import build_system_prompt
    from ui.console import console, print_assistant, print_user

    llm = AnthropicClient(model=args.model)
    engine = Engine(
        llm_client=llm,
        system_prompt=build_system_prompt(),
        auto_approve=args.yes,
    )

    console.print(f"\n[bold cyan]Agentic Coder[/] ({args.model})")
    console.print("[dim]Type 'q' or 'exit' to quit.[/]\n")

    while True:
        try:
            query = input("\033[36m>> \033[0m")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if query.strip().lower() in ("q", "exit", ""):
            break

        result = engine.run(query)
        if result:
            print_assistant(result)
            print()


if __name__ == "__main__":
    main()
