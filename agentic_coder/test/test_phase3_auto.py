"""Phase 3 automated tests: State, Tasks, Orchestrator, Commands.

Run: python -m pytest test/test_phase3_auto.py -v
"""

import json
import os
import sys
import time
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── State tests ────────────────────────────────────────────────────────

def test_state_init_empty():
    """init_state creates a valid State with empty defaults."""
    import core.state as state_mod
    state_mod._state = None
    s = state_mod.init_state()
    assert isinstance(s.permissions, dict)
    assert len(s.permissions) == 0
    assert isinstance(s.coder_rules, str)
    assert s.llm is None


def test_add_and_remove_permission():
    """add_permission writes to file; remove_permission deletes."""
    import core.state as state_mod
    state_mod._state = None
    state_mod.init_state()

    state_mod.add_permission("write_file", "C:/test", "test desc")
    assert "write_file:C:/test" in state_mod.get_state().permissions
    assert state_mod.get_state().permissions["write_file:C:/test"].description == "test desc"

    # Verify file written
    data = json.loads(state_mod.PERMISSIONS_FILE.read_text(encoding="utf-8"))
    assert "write_file:C:/test" in data

    # Remove
    removed = state_mod.remove_permission("write_file:C:/test")
    assert removed is True
    assert "write_file:C:/test" not in state_mod.get_state().permissions

    state_mod.PERMISSIONS_FILE.unlink(missing_ok=True)


def test_remove_nonexistent_permission():
    """remove_permission returns False for unknown key."""
    import core.state as state_mod
    state_mod._state = None
    state_mod.init_state()
    assert state_mod.remove_permission("nonexistent:key") is False


def test_permissions_persistence():
    """Permissions survive init_state reload."""
    import core.state as state_mod

    # Add a permission
    state_mod._state = None
    state_mod.init_state()
    state_mod.add_permission("run_command", "git push", "allow git push")

    # Reload state
    state_mod._state = None
    state_mod.init_state()
    assert "run_command:git push" in state_mod.get_state().permissions

    # Cleanup
    state_mod.remove_permission("run_command:git push")
    state_mod._state = None


def test_corrupted_permissions_file():
    """Corrupted permissions.json returns empty dict, no crash."""
    import core.state as state_mod
    state_mod._state = None

    state_mod.PERMISSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    state_mod.PERMISSIONS_FILE.write_text("not valid json", encoding="utf-8")

    s = state_mod.init_state()
    assert s.permissions == {}

    state_mod.PERMISSIONS_FILE.unlink(missing_ok=True)


def test_coder_rules_loading(tmp_path):
    """Coder rules loaded from global and project files."""
    import core.state as state_mod

    # Create temp rules files
    global_rules = tmp_path / "global_rules"
    project_rules = tmp_path / "project_rules"
    global_rules.write_text("Global rule", encoding="utf-8")
    project_rules.write_text("Project rule", encoding="utf-8")

    with patch.object(state_mod, "GLOBAL_RULES", global_rules), \
         patch.object(state_mod, "PROJECT_RULES", project_rules):
        state_mod._state = None
        s = state_mod.init_state()
        assert "Global rule" in s.coder_rules
        assert "Project rule" in s.coder_rules


def test_coder_rules_missing_files():
    """Missing .coder-rules files return empty string."""
    import core.state as state_mod
    state_mod._state = None

    with patch.object(state_mod, "GLOBAL_RULES", Path("/nonexistent/global")), \
         patch.object(state_mod, "PROJECT_RULES", Path("/nonexistent/project")):
        s = state_mod.init_state()
        assert s.coder_rules == ""


def test_get_state_before_init():
    """get_state raises RuntimeError before init_state."""
    import core.state as state_mod
    state_mod._state = None
    try:
        state_mod.get_state()
        assert False, "Should have raised RuntimeError"
    except RuntimeError:
        pass


# ── Tasks tests ────────────────────────────────────────────────────────

def test_task_runner_start_and_check():
    """Start a task, poll until done, verify output."""
    import core.tasks as tasks_mod
    tasks_mod._runner = None
    runner = tasks_mod.get_task_runner()

    tid = runner.start('python -u -c "print(42)"')
    assert tid.startswith("task_")

    time.sleep(0.5)
    r = runner.check(tid)
    assert r["task_id"] == tid
    assert r["status"] in ("running", "done")
    assert r["command"] == 'python -u -c "print(42)"'

    time.sleep(1)
    r = runner.check(tid)
    assert r["status"] == "done"
    assert r["exit_code"] == 0
    assert "42" in r["stdout"]

    runner.cleanup_all()
    tasks_mod._runner = None


def test_task_runner_max_concurrent():
    """6th concurrent task raises RuntimeError."""
    import core.tasks as tasks_mod
    tasks_mod._runner = None
    runner = tasks_mod.get_task_runner()

    for i in range(tasks_mod.MAX_CONCURRENT):
        runner.start("python -u -c \"import time; time.sleep(10)\"")

    try:
        runner.start("echo fail")
        assert False, "Should have raised RuntimeError"
    except RuntimeError:
        pass

    runner.cleanup_all()
    tasks_mod._runner = None


def test_task_runner_check_unknown():
    """check() returns error dict for unknown task_id."""
    import core.tasks as tasks_mod
    tasks_mod._runner = None
    runner = tasks_mod.get_task_runner()

    r = runner.check("task_999")
    assert "error" in r
    assert "Unknown task" in r["error"]

    tasks_mod._runner = None


def test_task_runner_list_all():
    """list_all returns all tasks with correct fields."""
    import core.tasks as tasks_mod
    tasks_mod._runner = None
    runner = tasks_mod.get_task_runner()

    runner.start('python -u -c "print(1)"')
    time.sleep(0.3)

    all_tasks = runner.list_all()
    assert len(all_tasks) >= 1
    t = all_tasks[0]
    assert "task_id" in t
    assert "command" in t
    assert "status" in t
    assert "exit_code" in t

    runner.cleanup_all()
    tasks_mod._runner = None


def test_task_runner_cleanup():
    """cleanup_all removes temp files."""
    import core.tasks as tasks_mod
    tasks_mod._runner = None
    runner = tasks_mod.get_task_runner()

    tid = runner.start('python -u -c "print(1)"')
    log_path = runner.tasks[tid].log_path
    assert os.path.exists(log_path)

    time.sleep(0.5)
    runner.cleanup_all()
    assert not os.path.exists(log_path)
    tasks_mod._runner = None


def test_task_runner_invalid_command():
    """Invalid command returns RuntimeError."""
    import core.tasks as tasks_mod
    tasks_mod._runner = None
    runner = tasks_mod.get_task_runner()

    try:
        runner.start("nonexistent_command_xyz_123")
        time.sleep(0.5)
        tid = runner.tasks[list(runner.tasks.keys())[0]].id
        r = runner.check(tid)
        assert r["status"] == "failed"
    except RuntimeError:
        pass

    runner.cleanup_all()
    tasks_mod._runner = None


# ── Orchestrator tests (offline) ────────────────────────────────────────

def test_build_child_prompt():
    """_build_child_prompt contains the task description."""
    from core.orchestrator import _build_child_prompt
    prompt = _build_child_prompt("Find all TODO comments")
    assert "Find all TODO comments" in prompt
    assert "ONLY goal" in prompt


def test_filter_tools():
    """_filter_tools returns only allowed tools."""
    import tools.fs  # noqa: F401
    import tools.shell  # noqa: F401
    import tools.agent_tools  # noqa: F401

    from core.orchestrator import _filter_tools
    filtered = _filter_tools(["read_file", "grep_search"])
    names = [t["name"] for t in filtered]
    assert names == ["read_file", "grep_search"]


def test_filter_tools_empty():
    """_filter_tools with empty list returns empty."""
    from core.orchestrator import _filter_tools
    assert _filter_tools([]) == []


# ── Agent tools registration ────────────────────────────────────────────

def test_agent_tools_registered():
    """All Phase 3 tools are registered in TOOL_REGISTRY."""
    import tools.fs  # noqa: F401
    import tools.shell  # noqa: F401
    import tools.git  # noqa: F401
    import tools.agent_tools  # noqa: F401

    from tools.registry import TOOL_REGISTRY
    assert "run_background" in TOOL_REGISTRY
    assert "check_task_logs" in TOOL_REGISTRY
    assert "delegate_task" in TOOL_REGISTRY


# ── Commands tests ─────────────────────────────────────────────────────

def test_permissions_command_registered():
    """/permissions and /tasks are registered."""
    from core.commands import COMMANDS
    assert "permissions" in COMMANDS
    assert "tasks" in COMMANDS


def test_delegate_task_truncation():
    """delegate_task truncates results over 4000 chars."""
    import tools.agent_tools as agent_mod

    long_text = "x" * 5000
    with patch("core.orchestrator.run_sub_agent", return_value=long_text):
        result = agent_mod.delegate_task("test", None)
        assert len(result) < 4100
        assert result.endswith("...[Truncated]")


# ── Prompts integration ────────────────────────────────────────────────

def test_prompts_injects_coder_rules(tmp_path):
    """build_system_prompt includes <project_rules> when coder rules exist."""
    import core.state as state_mod

    rules_file = tmp_path / ".coder-rules"
    rules_file.write_text("Always use black formatter", encoding="utf-8")

    state_mod._state = None
    with patch.object(state_mod, "PROJECT_RULES", rules_file), \
         patch.object(state_mod, "GLOBAL_RULES", Path("/nonexistent")):
        state_mod.init_state()

    from core.prompts import build_system_prompt
    prompt = build_system_prompt()
    assert "<project_rules>" in prompt
    assert "Always use black formatter" in prompt
    state_mod._state = None


def test_prompts_no_rules_section_when_empty():
    """build_system_prompt omits <project_rules> when no rules."""
    import core.state as state_mod
    state_mod._state = None
    with patch.object(state_mod, "GLOBAL_RULES", Path("/nonexistent")), \
         patch.object(state_mod, "PROJECT_RULES", Path("/nonexistent")):
        state_mod.init_state()

    from core.prompts import build_system_prompt
    prompt = build_system_prompt()
    assert "<project_rules>" not in prompt
    state_mod._state = None


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
