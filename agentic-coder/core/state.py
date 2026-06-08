"""Global state singleton: permissions + coder rules."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

PERMISSIONS_FILE = Path.home() / ".agentic-coder" / "permissions.json"
GLOBAL_RULES = Path.home() / ".coder-rules"
PROJECT_RULES = Path.cwd() / ".coder-rules"


class PermissionRule(BaseModel):
    tool_name: str
    pattern: str
    description: str = ""


class State(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    permissions: dict[str, PermissionRule] = {}
    coder_rules: str = ""
    llm: object | None = None


_state: State | None = None


def get_state() -> State:
    if _state is None:
        raise RuntimeError("State not initialized. Call init_state() first.")
    return _state


def init_state() -> State:
    global _state
    _state = State()
    _state.permissions = _load_permissions()
    _state.coder_rules = _load_coder_rules()
    return _state


def _load_permissions() -> dict[str, PermissionRule]:
    if not PERMISSIONS_FILE.exists():
        return {}
    try:
        raw = json.loads(PERMISSIONS_FILE.read_text(encoding="utf-8", errors="replace"))
        return {k: PermissionRule(**v) for k, v in raw.items()}
    except (json.JSONDecodeError, OSError):
        return {}


def save_permissions() -> None:
    state = get_state()
    PERMISSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {k: v.model_dump() for k, v in state.permissions.items()}
    PERMISSIONS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def add_permission(tool_name: str, pattern: str, description: str = "") -> None:
    key = f"{tool_name}:{pattern}"
    get_state().permissions[key] = PermissionRule(
        tool_name=tool_name, pattern=pattern, description=description,
    )
    save_permissions()


def remove_permission(key: str) -> bool:
    state = get_state()
    if key in state.permissions:
        del state.permissions[key]
        save_permissions()
        return True
    return False


def _load_coder_rules() -> str:
    parts = []
    for path in (GLOBAL_RULES, PROJECT_RULES):
        if path.exists():
            try:
                parts.append(path.read_text(encoding="utf-8", errors="replace").strip())
            except OSError:
                pass
    return "\n\n".join(parts)


def reload_coder_rules() -> str:
    rules = _load_coder_rules()
    get_state().coder_rules = rules
    return rules
