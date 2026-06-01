"""User input with prompt_toolkit: multi-line support, paste-safe."""

from __future__ import annotations

from prompt_toolkit import ANSI, PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.patch_stdout import patch_stdout

_bindings = KeyBindings()


@_bindings.add("enter")
def _(event):
    """Enter submits the input."""
    event.current_buffer.validate_and_handle()


@_bindings.add("escape", "enter")
def _(event):
    """Alt+Enter inserts a newline."""
    event.current_buffer.newline()


# Shift+Enter handling varies by terminal; Alt+Enter is the reliable fallback.
_session: PromptSession | None = None


def _get_session() -> PromptSession:
    global _session
    if _session is None:
        _session = PromptSession(key_bindings=_bindings)
    return _session


def get_input(prompt: str = "\033[36m>> \033[0m") -> str | None:
    """Read user input with prompt_toolkit.

    - Enter: submit
    - Alt+Enter: insert newline (for multi-line input)
    - Ctrl+C / Ctrl+D: return None (exit signal)

    Returns None when the user wants to exit.
    """
    try:
        with patch_stdout():
            return _get_session().prompt(ANSI(prompt))
    except KeyboardInterrupt:
        return None
    except EOFError:
        return None
