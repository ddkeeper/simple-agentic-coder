#!/usr/bin/env python3
"""CLI entry point for simple-coding-agent."""

import argparse
import os

from dotenv import load_dotenv

from .config import build_config
from .loop import agent_loop, build_system_prompt


def parse_args():
    p = argparse.ArgumentParser(description="Simple Agentic Coder")
    p.add_argument("--model", default=os.getenv("MODEL_ID", "claude-sonnet-4-20250514"))
    p.add_argument("--yes", action="store_true", help="Auto-approve all tool calls")
    p.add_argument("--max-tokens", type=int, default=8000)
    return p.parse_args()


def main():
    load_dotenv(override=True)
    args = parse_args()
    config = build_config(args)
    system = build_system_prompt(config)

    print(f"Simple Agentic Coder ({config['model']})")
    print("Type 'q' or 'exit' to quit.\n")

    history = []
    while True:
        try:
            query = input("\033[36m>> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break

        history.append({"role": "user", "content": query})
        agent_loop(history, system=system, config=config)

        # Print final text response
        last = history[-1]["content"]
        if isinstance(last, list):
            for block in last:
                if hasattr(block, "text"):
                    print(block.text)
        print()


if __name__ == "__main__":
    main()
