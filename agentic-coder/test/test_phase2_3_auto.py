"""Phase 2.3 automated tests: slash commands + session persistence (offline).

Run:  python test/test_phase2_3_auto.py
No API key required — all tests are offline with mocks.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

# Ensure agentic-coder root is on sys.path
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_passed = 0
_failed = 0


def _section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def _ok(name: str, detail: str = "") -> None:
    global _passed
    _passed += 1
    suffix = f"  ({detail})" if detail else ""
    print(f"  [PASS] {name}{suffix}")


def _fail(name: str, detail: str = "") -> None:
    global _failed
    _failed += 1
    suffix = f"  ({detail})" if detail else ""
    print(f"  [FAIL] {name}{suffix}")


def _make_mock_engine() -> MagicMock:
    """Create a mock Engine with messages list and llm.model."""
    engine = MagicMock()
    engine.messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": [{"type": "text", "text": "hi!"}]},
    ]
    engine.llm.model = "test-model"
    return engine


# ===================================================================
# 2.3-A  Slash commands
# ===================================================================

def test_command_registration():
    """Built-in commands are registered: /clear, /compact, /exit, /help, /resume, /sessions."""
    _section("2.3-A  command registration")
    from core.commands import COMMANDS, list_commands

    expected = {"clear", "compact", "exit", "help", "resume", "sessions"}
    registered = set(COMMANDS.keys())
    missing = expected - registered
    if missing:
        _fail("all commands registered", f"missing: {missing}")
    else:
        _ok("all commands registered", f"{len(registered)} commands: {list_commands()}")


def test_handle_input_non_command():
    """Normal text passes through unchanged."""
    _section("2.3-B  handle_input passthrough")
    from core.commands import handle_input

    engine = _make_mock_engine()
    result = handle_input("What is Python?", engine)
    if result == "What is Python?":
        _ok("non-command passthrough", repr(result))
    else:
        _fail("non-command passthrough", repr(result))


def test_handle_input_command():
    """Slash commands return None (handled)."""
    _section("2.3-C  handle_input intercepts commands")
    from core.commands import handle_input

    engine = _make_mock_engine()
    result = handle_input("/help", engine)
    if result is None:
        _ok("/help returns None")
    else:
        _fail("/help returns None", repr(result))


def test_cmd_clear():
    """/clear empties engine.messages."""
    _section("2.3-D  /clear command")
    from core.commands import handle_input

    engine = _make_mock_engine()
    assert len(engine.messages) == 2
    handle_input("/clear", engine)
    if len(engine.messages) == 0:
        _ok("/clear empties messages")
    else:
        _fail("/clear empties messages", f"len={len(engine.messages)}")


def test_cmd_exit():
    """/exit raises SystemExit."""
    _section("2.3-E  /exit command")
    from core.commands import handle_input

    engine = _make_mock_engine()
    try:
        handle_input("/exit", engine)
        _fail("/exit raises SystemExit", "no exception raised")
    except SystemExit:
        _ok("/exit raises SystemExit")


def test_unknown_command():
    """Unknown /command prints error and returns None."""
    _section("2.3-F  unknown command")
    from core.commands import handle_input

    engine = _make_mock_engine()
    result = handle_input("/foobar", engine)
    if result is None:
        _ok("unknown command returns None")
    else:
        _fail("unknown command returns None", repr(result))


def test_cmd_sessions_empty():
    """/sessions on empty dir shows no error."""
    _section("2.3-H  /sessions (empty)")
    from core.commands import handle_input
    from core.session import list_sessions

    tmpdir = tempfile.mkdtemp()
    import core.session as session_mod
    orig_dir = session_mod.SESSION_DIR
    session_mod.SESSION_DIR = Path(tmpdir)

    try:
        sessions = list_sessions()
        if sessions == []:
            _ok("/sessions empty returns []")
        else:
            _fail("/sessions empty returns []", repr(sessions))
    finally:
        session_mod.SESSION_DIR = orig_dir
        shutil.rmtree(tmpdir, ignore_errors=True)


# ===================================================================
# 2.3-I  Session persistence
# ===================================================================

def test_save_and_load_session():
    """save_session -> load_session roundtrip."""
    _section("2.3-I  save/load roundtrip")
    from core.session import load_session, save_session

    import core.session as session_mod
    tmpdir = tempfile.mkdtemp()
    orig_dir = session_mod.SESSION_DIR
    session_mod.SESSION_DIR = Path(tmpdir)

    try:
        engine = _make_mock_engine()
        save_session(engine, "test_roundtrip")

        data = load_session("test_roundtrip")
        if data is None:
            _fail("load returns data", "None")
            return

        checks = [
            (len(data["messages"]) == 2, f"messages={len(data['messages'])}"),
            (data["model"] == "test-model", f"model={data['model']}"),
            (isinstance(data["timestamp"], float), "timestamp is float"),
        ]
        for ok_flag, desc in checks:
            _ok(desc) if ok_flag else _fail(desc)
    finally:
        session_mod.SESSION_DIR = orig_dir
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_load_nonexistent_session():
    """load_session returns None for non-existent name."""
    _section("2.3-J  load non-existent session")
    from core.session import load_session

    import core.session as session_mod
    tmpdir = tempfile.mkdtemp()
    orig_dir = session_mod.SESSION_DIR
    session_mod.SESSION_DIR = Path(tmpdir)

    try:
        result = load_session("does_not_exist")
        if result is None:
            _ok("non-existent returns None")
        else:
            _fail("non-existent returns None", repr(result))
    finally:
        session_mod.SESSION_DIR = orig_dir
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_list_sessions():
    """list_sessions returns sorted entries (newest first)."""
    _section("2.3-K  list_sessions")
    import time

    from core.session import list_sessions, save_session

    import core.session as session_mod
    tmpdir = tempfile.mkdtemp()
    orig_dir = session_mod.SESSION_DIR
    session_mod.SESSION_DIR = Path(tmpdir)

    try:
        engine = _make_mock_engine()
        save_session(engine, "alpha")
        time.sleep(0.05)
        engine.messages.append({"role": "user", "content": "second"})
        save_session(engine, "beta")

        sessions = list_sessions()
        checks = [
            (len(sessions) == 2, f"count={len(sessions)}"),
            (sessions[0]["name"] == "beta", f"newest first: {sessions[0]['name']}"),
            (sessions[1]["name"] == "alpha", f"oldest second: {sessions[1]['name']}"),
            (sessions[0]["message_count"] == 3, f"beta msgs={sessions[0]['message_count']}"),
        ]
        for ok_flag, desc in checks:
            _ok(desc) if ok_flag else _fail(desc)
    finally:
        session_mod.SESSION_DIR = orig_dir
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_save_overwrites():
    """Saving with same name overwrites previous file."""
    _section("2.3-L  save overwrites")
    from core.session import load_session, save_session

    import core.session as session_mod
    tmpdir = tempfile.mkdtemp()
    orig_dir = session_mod.SESSION_DIR
    session_mod.SESSION_DIR = Path(tmpdir)

    try:
        engine = _make_mock_engine()
        save_session(engine, "overwrite_test")

        engine.messages.append({"role": "user", "content": "more"})
        save_session(engine, "overwrite_test")

        data = load_session("overwrite_test")
        if data and len(data["messages"]) == 3:
            _ok("overwrite preserves latest", f"msgs={len(data['messages'])}")
        else:
            _fail("overwrite preserves latest", f"msgs={len(data.get('messages', [])) if data else 'None'}")
    finally:
        session_mod.SESSION_DIR = orig_dir
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_corrupted_session_file():
    """Corrupted JSON returns None gracefully."""
    _section("2.3-M  corrupted session file")
    from core.session import load_session

    import core.session as session_mod
    tmpdir = tempfile.mkdtemp()
    orig_dir = session_mod.SESSION_DIR
    session_mod.SESSION_DIR = Path(tmpdir)

    try:
        bad_path = Path(tmpdir) / "corrupted.json"
        bad_path.write_text("{invalid json!!!", encoding="utf-8")

        result = load_session("corrupted")
        if result is None:
            _ok("corrupted returns None")
        else:
            _fail("corrupted returns None", repr(result))
    finally:
        session_mod.SESSION_DIR = orig_dir
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_session_with_complex_content():
    """Session roundtrip with tool_result content blocks."""
    _section("2.3-N  complex content roundtrip")
    from core.session import load_session, save_session

    import core.session as session_mod
    tmpdir = tempfile.mkdtemp()
    orig_dir = session_mod.SESSION_DIR
    session_mod.SESSION_DIR = Path(tmpdir)

    try:
        engine = _make_mock_engine()
        engine.messages = [
            {"role": "user", "content": "read main.py"},
            {"role": "assistant", "content": [
                {"type": "text", "text": "Let me read it."},
                {"type": "tool_use", "id": "tu_1", "name": "read_file",
                 "input": {"path": "main.py"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_1",
                 "content": "print('hello')", "_tool_name": "read_file"},
            ]},
            {"role": "assistant", "content": [
                {"type": "text", "text": "The file contains print('hello')."},
            ]},
        ]

        save_session(engine, "complex")
        data = load_session("complex")

        if data is None:
            _fail("complex roundtrip", "load returned None")
            return

        msgs = data["messages"]
        tool_use_block = msgs[1]["content"][1]
        tool_result_block = msgs[2]["content"][0]
        checks = [
            (len(msgs) == 4, f"4 messages: {len(msgs)}"),
            (tool_use_block["name"] == "read_file", f"tool_use name: {tool_use_block['name']}"),
            (tool_result_block["_tool_name"] == "read_file", f"_tool_name preserved"),
            (tool_result_block["content"] == "print('hello')", f"tool_result content"),
        ]
        for ok_flag, desc in checks:
            _ok(desc) if ok_flag else _fail(desc)
    finally:
        session_mod.SESSION_DIR = orig_dir
        shutil.rmtree(tmpdir, ignore_errors=True)


# ===================================================================
# main
# ===================================================================

if __name__ == "__main__":
    print("Phase 2.3 Automated Tests (offline)")
    print("=" * 60)

    # --- slash commands ---
    test_command_registration()
    test_handle_input_non_command()
    test_handle_input_command()
    test_cmd_clear()
    test_cmd_exit()
    test_unknown_command()
    test_cmd_sessions_empty()

    # --- session persistence ---
    test_save_and_load_session()
    test_load_nonexistent_session()
    test_list_sessions()
    test_save_overwrites()
    test_corrupted_session_file()
    test_session_with_complex_content()

    # --- summary ---
    print(f"\n{'=' * 60}")
    print(f"  Results:  {_passed} passed,  {_failed} failed")
    print(f"{'=' * 60}")
    sys.exit(1 if _failed else 0)
