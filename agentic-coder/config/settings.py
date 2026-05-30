"""Runtime configuration: .env loading and argparse."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Agentic Coder - AI coding agent")
    p.add_argument("--model", default=os.getenv("MODEL_ID", "claude-sonnet-4-20250514"))
    p.add_argument("--yes", action="store_true", help="Auto-approve all tool calls")
    return p.parse_args()


def load_env() -> None:
    """Load .env file from project root, overriding existing env vars."""
    load_dotenv(_PROJECT_ROOT / ".env", override=True)
