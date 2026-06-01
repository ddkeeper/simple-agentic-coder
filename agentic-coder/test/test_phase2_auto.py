"""Phase 2 automated tests (offline + live API).

Run:  python test/test_phase2_auto.py
Requires: ANTHROPIC_API_KEY in .env, all deps installed.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

# Ensure agentic-coder root is on sys.path
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv(_ROOT / ".env", override=True)

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


# ===================================================================
# Phase 2.2  --  工具注册 & glob/grep（纯离线，不需要 API）
# ===================================================================

def test_tool_registration():
    """6 个工具全部正确注册，schema 含预期参数。"""
    _section("2.2-A  tool registration")
    import tools.fs  # noqa: F401  triggers @tool registration
    import tools.git  # noqa: F401
    import tools.shell  # noqa: F401
    from tools.registry import get_anthropic_tools

    tools_list = get_anthropic_tools()
    names = {t["name"] for t in tools_list}
    expected = {"read_file", "write_file", "edit_file", "list_files",
                "glob_search", "grep_search", "run_command", "git_log"}
    missing = expected - names
    if missing:
        _fail("all tools registered", f"missing: {missing}")
    else:
        _ok("all tools registered", f"{len(tools_list)} tools")

    # spot-check parameter names
    by_name = {t["name"]: t for t in tools_list}
    checks = [
        ("glob_search", ["pattern", "path"]),
        ("grep_search", ["pattern", "path", "glob"]),
    ]
    for tname, expected_params in checks:
        props = list(by_name[tname]["input_schema"]["properties"].keys())
        if props == expected_params:
            _ok(f"{tname} params", str(props))
        else:
            _fail(f"{tname} params", f"got {props}, want {expected_params}")


def test_glob_search():
    """glob_search 能匹配当前目录的 .py 文件。"""
    _section("2.2-B  glob_search")
    from tools.registry import execute_tool

    result = execute_tool("glob_search", {"pattern": "*.py", "path": str(_ROOT)})
    if "main.py" in result:
        _ok("glob *.py", "found main.py")
    else:
        _fail("glob *.py", f"unexpected: {result[:200]}")


def test_grep_search():
    """grep_search 能匹配 def 关键字，且单行截断到 200 字符。"""
    _section("2.2-C  grep_search")
    from tools.registry import execute_tool

    # basic match
    result = execute_tool("grep_search", {
        "pattern": "def ",
        "path": str(_ROOT),
        "glob": "main.py",
    })
    if "def " in result:
        _ok("grep def in main.py")
    else:
        _fail("grep def in main.py", result[:200])

    # line truncation: create temp file with a 500-char line containing NEEDLE
    tmpdir = tempfile.mkdtemp()
    try:
        long_line = "a" * 500 + "NEEDLE" + "b" * 500
        Path(tmpdir, "long.py").write_text(f"short\n{long_line}\nend\n")

        result = execute_tool("grep_search", {
            "pattern": "NEEDLE",
            "path": tmpdir,
            "glob": "*.py",
        })
        matched_part = result.split(": ", 1)[-1] if ": " in result else result
        if "..." in matched_part and len(matched_part) <= 210:
            _ok("line truncation", f"{len(matched_part)} chars")
        else:
            _fail("line truncation", f"len={len(matched_part)}, has ...: {'...' in matched_part}")
    finally:
        shutil.rmtree(tmpdir)


# ===================================================================
# Phase 2.1  --  数据结构 & 渲染（离线 mock）
# ===================================================================

def test_stream_dataclasses():
    """StreamContext / StreamEvent 正确实例化。"""
    _section("2.1-A  StreamContext & StreamEvent")
    from core.llm import StreamContext, StreamEvent

    ctx = StreamContext()
    assert ctx.text == ""
    assert ctx.interrupted is False
    assert ctx.stop_reason == ""
    assert ctx.content_blocks == []
    _ok("StreamContext defaults")

    evt = StreamEvent(type="text_delta", text="hello")
    assert evt.type == "text_delta"
    assert evt.text == "hello"
    _ok("StreamEvent fields")


def test_print_token_usage(capsys=None):
    """print_token_usage 格式化输出。"""
    _section("2.1-B  print_token_usage")
    from ui.console import print_token_usage

    # just verify it doesn't raise
    print_token_usage({"input_tokens": 12345, "output_tokens": 678})
    _ok("format", "no exception raised")


def test_stream_print_mock():
    """stream_print 正确消费 mock generator 并返回拼接文本。"""
    _section("2.1-C  stream_print (mock)")
    from core.llm import StreamContext, StreamEvent
    from ui.console import stream_print

    def mock_gen():
        ctx = StreamContext(text="")
        yield ctx, StreamEvent(type="stream_start")
        yield ctx, StreamEvent(type="text_delta", text="Hello ")
        yield ctx, StreamEvent(type="text_delta", text="world!")
        yield ctx, StreamEvent(type="stream_end")

    # stream_print expects the generator AFTER stream_start
    gen = mock_gen()
    ctx, _ = next(gen)  # consume stream_start
    text = stream_print(gen)

    if text == "Hello world!":
        _ok("text accumulation", repr(text))
    else:
        _fail("text accumulation", repr(text))


# ===================================================================
# Phase 2.1  --  流式 API 调用（需要真实 API）
# ===================================================================

def test_stream_text_only():
    """流式纯文本输出：stop_reason=end_turn, text 非空。"""
    _section("2.1-D  streaming text (live API)")
    from core.llm import AnthropicClient
    from ui.console import stream_print

    llm = AnthropicClient(model=os.getenv("MODEL_ID", "claude-sonnet-4-20250514"))
    gen = llm.send_stream(
        system="Reply in one short sentence. No emojis.",
        messages=[{"role": "user", "content": "What is 2+2?"}],
    )
    ctx, evt = next(gen)
    assert evt.type == "stream_start"
    text = stream_print(gen)

    checks = [
        (bool(text), "text non-empty"),
        (text == ctx.text, "text == ctx.text"),
        (ctx.stop_reason == "end_turn", f"stop_reason={ctx.stop_reason}"),
        (not ctx.interrupted, "not interrupted"),
    ]
    for ok_flag, desc in checks:
        _ok(desc) if ok_flag else _fail(desc)


def test_stream_tool_use():
    """流式 tool_use：模型调用 glob_search。"""
    _section("2.1-E  streaming tool_use (live API)")
    import tools.fs  # noqa: F401
    from core.llm import AnthropicClient
    from tools.registry import get_anthropic_tools
    from ui.console import stream_print

    llm = AnthropicClient(model=os.getenv("MODEL_ID", "claude-sonnet-4-20250514"))
    gen = llm.send_stream(
        system="You are a coding assistant. Use tools when asked.",
        messages=[{"role": "user", "content":
                   "Use glob_search to find all *.py files in the current directory."}],
        tools=get_anthropic_tools(),
    )
    ctx, _ = next(gen)
    stream_print(gen)

    has_tool = any(getattr(b, "type", None) == "tool_use" for b in ctx.content_blocks)
    checks = [
        (ctx.stop_reason == "tool_use", f"stop_reason={ctx.stop_reason}"),
        (has_tool, "has tool_use block"),
    ]
    for ok_flag, desc in checks:
        _ok(desc) if ok_flag else _fail(desc)


def test_stream_token_usage():
    """流式输出后 ctx.usage 包含 input/output tokens。"""
    _section("2.1-F  streaming token capture (live API)")
    from core.llm import AnthropicClient
    from ui.console import stream_print

    llm = AnthropicClient(model=os.getenv("MODEL_ID", "claude-sonnet-4-20250514"))
    gen = llm.send_stream(
        system="Reply briefly. No emojis.",
        messages=[{"role": "user", "content": "Say OK"}],
    )
    ctx, _ = next(gen)
    stream_print(gen)

    checks = [
        ("input_tokens" in ctx.usage, f"input_tokens={ctx.usage.get('input_tokens')}"),
        ("output_tokens" in ctx.usage, f"output_tokens={ctx.usage.get('output_tokens')}"),
    ]
    for ok_flag, desc in checks:
        _ok(desc) if ok_flag else _fail(desc)


# ===================================================================
# Phase 2.1  --  engine.run() 完整链路（需要真实 API）
# ===================================================================

def test_engine_text():
    """engine.run() 纯文本响应。"""
    _section("2.1-G  engine.run text-only (live API)")
    import tools.fs, tools.shell, tools.git  # noqa: F401
    from core.engine import Engine
    from core.llm import AnthropicClient
    from core.prompts import build_system_prompt

    llm = AnthropicClient(model=os.getenv("MODEL_ID", "claude-sonnet-4-20250514"))
    engine = Engine(llm_client=llm, system_prompt=build_system_prompt(), auto_approve=True)

    result = engine.run("What is 3+5? Reply with just the number.")
    checks = [
        (bool(result), "result non-empty"),
        ("8" in result, f"contains '8': {result!r}"),
        (len(engine.messages) == 2, f"messages={len(engine.messages)}"),
    ]
    for ok_flag, desc in checks:
        _ok(desc) if ok_flag else _fail(desc)


def test_engine_tool_loop():
    """engine.run() 触发工具调用完整循环。"""
    _section("2.1-H  engine.run tool loop (live API)")
    import tools.fs, tools.shell, tools.git  # noqa: F401
    from core.engine import Engine
    from core.llm import AnthropicClient
    from core.prompts import build_system_prompt

    llm = AnthropicClient(model=os.getenv("MODEL_ID", "claude-sonnet-4-20250514"))
    engine = Engine(llm_client=llm, system_prompt=build_system_prompt(), auto_approve=True)

    result = engine.run("Read requirements.txt and tell me the first line.")
    has_tool_result = any(
        isinstance(m.get("content"), list) and any(
            isinstance(b, dict) and b.get("type") == "tool_result"
            for b in m["content"]
        )
        for m in engine.messages
    )
    checks = [
        (has_tool_result, "tool_result in messages"),
        ("anthropic" in result.lower(), f"answer mentions anthropic: {result!r}"),
    ]
    for ok_flag, desc in checks:
        _ok(desc) if ok_flag else _fail(desc)


def test_engine_multi_turn():
    """多轮对话上下文保持。"""
    _section("2.1-I  engine.run multi-turn (live API)")
    import tools.fs, tools.shell, tools.git  # noqa: F401
    from core.engine import Engine
    from core.llm import AnthropicClient
    from core.prompts import build_system_prompt

    llm = AnthropicClient(model=os.getenv("MODEL_ID", "claude-sonnet-4-20250514"))
    engine = Engine(llm_client=llm, system_prompt=build_system_prompt(), auto_approve=True)

    engine.run("Remember the number 42. Just say OK.")
    result = engine.run("What number did I ask you to remember?")

    checks = [
        ("42" in result, f"contains '42': {result!r}"),
        (len(engine.messages) == 4, f"messages={len(engine.messages)}"),
    ]
    for ok_flag, desc in checks:
        _ok(desc) if ok_flag else _fail(desc)


# ===================================================================
# main
# ===================================================================

if __name__ == "__main__":
    print("Phase 2 Automated Tests")
    print("=" * 60)

    # --- offline tests (no API needed) ---
    test_tool_registration()
    test_glob_search()
    test_grep_search()
    test_stream_dataclasses()
    test_print_token_usage()
    test_stream_print_mock()

    # --- live API tests ---
    test_stream_text_only()
    test_stream_tool_use()
    test_stream_token_usage()
    test_engine_text()
    test_engine_tool_loop()
    test_engine_multi_turn()

    # --- summary ---
    print(f"\n{'=' * 60}")
    print(f"  Results:  {_passed} passed,  {_failed} failed")
    print(f"{'=' * 60}")
    sys.exit(1 if _failed else 0)
