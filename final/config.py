#!/usr/bin/env python3
"""CLI args and environment config."""

import os
import platform
from datetime import datetime


def build_config(args) -> dict:
    return {
        "model": args.model,
        "max_tokens": args.max_tokens,
        "auto_approve": args.yes,
        "cwd": os.getcwd(),
        "platform": platform.system(),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "compact_threshold": 40_000,  # tokens
        "keep_recent": 6,             # messages to keep during compact
    }
