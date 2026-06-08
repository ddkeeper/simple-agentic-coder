"""Silent file logger for debugging API calls."""

import json
import os
import re
from datetime import datetime
from pathlib import Path


class Logger:
    def __init__(self, log_dir: str | None = None):
        if log_dir is None:
            log_dir = os.path.expanduser("~/.agentic-coder/logs")
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"{timestamp}.jsonl"

    def log(self, event_type: str, data: dict) -> None:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "data": self._scrub_secrets(data),
        }
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")

    @staticmethod
    def _scrub_secrets(data: dict) -> dict:
        text = json.dumps(data, ensure_ascii=False, default=str)
        text = re.sub(r"(sk-ant-|sk-)[a-zA-Z0-9_-]{20,}", "[REDACTED]", text)
        return json.loads(text)
