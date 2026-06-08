"""Background task runner with tempfile-based live logging."""

from __future__ import annotations

import atexit
import os
import subprocess
import tempfile
import time
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

MAX_CONCURRENT = 5
MAX_LOG_TAIL = 5000


class TaskState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class Task(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str
    command: str
    status: TaskState = TaskState.PENDING
    process: Any = None
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    created_at: float = 0.0
    finished_at: float = 0.0
    log_path: str = ""


class TaskRunner:
    def __init__(self):
        self.tasks: dict[str, Task] = {}
        self._counter = 0

    def start(self, command: str) -> str:
        self._reap()
        running = sum(1 for t in self.tasks.values() if t.status == TaskState.RUNNING)
        if running >= MAX_CONCURRENT:
            raise RuntimeError(
                f"Max {MAX_CONCURRENT} concurrent tasks reached. "
                "Wait for a task to finish or check with check_task_logs."
            )

        self._counter += 1
        task_id = f"task_{self._counter}"

        log_file = tempfile.NamedTemporaryFile(
            delete=False, suffix=".log", prefix=f"agentic_{task_id}_"
        )
        log_path = log_file.name

        try:
            proc = subprocess.Popen(
                command,
                shell=True,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                cwd=str(Path.cwd()),
            )
        except OSError as e:
            log_file.close()
            os.unlink(log_path)
            raise RuntimeError(f"Failed to start process: {e}") from e
        finally:
            log_file.close()

        self.tasks[task_id] = Task(
            id=task_id,
            command=command,
            status=TaskState.RUNNING,
            process=proc,
            created_at=time.time(),
            log_path=log_path,
        )
        return task_id

    def check(self, task_id: str) -> dict:
        task = self.tasks.get(task_id)
        if task is None:
            return {"error": f"Unknown task: {task_id}"}

        self._reap_one(task)
        log_tail = self._read_log_tail(task)

        return {
            "task_id": task.id,
            "command": task.command,
            "status": task.status.value,
            "stdout": log_tail,
            "exit_code": task.exit_code,
        }

    def list_all(self) -> list[dict]:
        self._reap()
        return [
            {
                "task_id": t.id,
                "command": t.command,
                "status": t.status.value,
                "exit_code": t.exit_code,
            }
            for t in self.tasks.values()
        ]

    def _read_log_tail(self, task: Task) -> str:
        if not task.log_path or not os.path.exists(task.log_path):
            return ""
        try:
            with open(task.log_path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(0, 2)
                size = f.tell()
                if size > MAX_LOG_TAIL:
                    f.seek(-MAX_LOG_TAIL, 2)
                else:
                    f.seek(0)
                return f.read().strip()
        except OSError:
            return ""

    def _reap(self) -> None:
        for task in list(self.tasks.values()):
            self._reap_one(task)

    def _reap_one(self, task: Task) -> None:
        if task.status != TaskState.RUNNING:
            return
        proc = task.process
        if proc is None:
            return
        ret = proc.poll()
        if ret is None:
            return
        task.exit_code = ret
        task.status = TaskState.DONE if ret == 0 else TaskState.FAILED
        task.finished_at = time.time()
        task.process = None

    def cleanup_all(self) -> None:
        for task in self.tasks.values():
            if task.process is not None:
                try:
                    task.process.kill()
                except OSError:
                    pass
                task.process = None
            if task.log_path and os.path.exists(task.log_path):
                try:
                    os.unlink(task.log_path)
                except OSError:
                    pass


_runner: TaskRunner | None = None


def get_task_runner() -> TaskRunner:
    global _runner
    if _runner is None:
        _runner = TaskRunner()
        atexit.register(_runner.cleanup_all)
    return _runner
