# Phase 3 开发计划 — State Layer + Task System + Orchestrator

## Context

Phase 2 已完成（v2.0-phase2）。当前 agent 支持 ReAct 循环、流式输出、prompt_toolkit 多行输入、Glob/Grep 搜索、Slash 命令、会话持久化。

依据 `dev_docs/document_v3.md`，Phase 3 分三个子阶段实现四层架构升维：状态层（持久化权限与规则注入）、任务系统（后台进程池）、编排器（子代理委派）。

## 关键设计决策

| 决策 | 选择 | 原因 |
|------|------|------|
| State 单例 | 模块级 `_state + get_state()` | 权限和规则需跨 hitl/prompts/commands 共享，单例最简洁 |
| LLM 客户端传递 | 存入 State.llm | 子代理通过 `get_state().llm` 获取，无需穿透工具层 |
| 子代理 ReAct 循环 | 独立实现（非复用 Engine.run） | 需静默执行、跳过 HITL、禁止 auto-commit、支持迭代上限/超时 |
| 子代理 HITL | 完全跳过 | 父代理已审批 `delegate_task` 调用，子代理无需二次确认 |
| 子代理流式 | 不使用 send_stream | 子代理静默执行，无需 UI 渲染 |
| 权限 key 格式 | `{tool_name}:{resolved_pattern}` | O(1) dict 查找，key 唯一可寻址 |
| 任务输出获取 | tempfile 重定向 + 尾部读取 | 进程运行中也能实时读取增量日志，真正"一边跑一边看" |
| 子代理超时保障 | 物理级 timeout（HTTP + subprocess） | 循环级超时无法覆盖阻塞调用，必须在 I/O 边界设强制超时 |
| 临时文件泄漏 | atexit 钩子兜底清理 | Ctrl+C 强退或崩溃时 `_reap_one()` 无法执行，atexit 确保临时日志文件不残留 |
| 子代理摘要溢出 | 薄壳层 4000 字符截断 | orchestrator 保持纯净，由 agent_tools 承担安全阀，防止主 Agent 上下文爆栈 |

## 涉及文件

### 新建文件（4 个）

| 文件 | 层级 | 说明 |
|------|------|------|
| `core/state.py` | Support | 全局状态单例：permissions + coder_rules + llm 引用 |
| `core/tasks.py` | Support | TaskRunner：subprocess.Popen 后台进程池，状态机管理 |
| `core/orchestrator.py` | Engine | 子代理委派：独立 ReAct 循环，过滤工具集，禁止 auto-commit |
| `tools/agent_tools.py` | Tools | 薄壳工具：run_background / check_task_logs / delegate_task |

### 修改文件（5 个）

| 文件 | Phase | 改动 |
|------|-------|------|
| `main.py` | 3.1+3.2+3.3 | `init_state()`、`import tools.agent_tools`、`get_state().llm = llm` |
| `core/prompts.py` | 3.1 | lazy import `get_state()`，追加 `<project_rules>` 块 |
| `ui/hitl.py` | 3.1 | 权限检查前置、`_build_pattern()`、`_ask_user` 增加 `a/always` 选项 |
| `core/commands.py` | 3.1+3.2 | 新增 `/permissions`、`/tasks` 命令 |
| `core/llm.py` | 3.3 | 构造函数增加 `timeout` 参数，传入 Anthropic 客户端，防止网络卡死 |
| `core/schemas.py` | — | 不改动，新模型就近放在 state.py 和 tasks.py |

---

## Phase 3.1：状态层

### Step 1：创建 `core/state.py`

独立模块，无外部依赖。

```python
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
    llm: AnthropicClient | None = None   # Phase 3.3 添加

# 单例
_state: State | None = None
get_state() -> State          # 未初始化时 raise RuntimeError
init_state() -> State         # 加载 permissions.json + .coder-rules
save_permissions() -> None    # 写入 permissions.json
add_permission(tool, pattern, desc) -> None
remove_permission(key) -> bool
reload_coder_rules() -> str   # 重新读取 .coder-rules 文件
```

权限 key 格式：`f"{tool_name}:{pattern}"`（如 `write_file:C:/external/path`）

### Step 2：修改 `core/prompts.py`

`build_system_prompt()` 末尾追加条件块：

```python
from core.state import get_state  # lazy import

state = get_state()
rules_section = ""
if state.coder_rules:
    rules_section = f"\n\n<project_rules>\n{state.coder_rules}\n</project_rules>"
# 追加到 return f"""...{rules_section}"""
```

### Step 3：修改 `ui/hitl.py`

在现有 HITL 逻辑**之前**插入权限检查：

```python
def check_approval(tool_name, tool_input):
    from core.state import get_state
    pattern = _build_pattern(tool_name, tool_input)
    key = f"{tool_name}:{pattern}"
    if key in get_state().permissions:
        return True
    # ... 现有逻辑不变 ...
```

`_ask_user` 新增 `tool_name`/`pattern` 参数，增加 `a/always` 选项：

```python
answer = input(f"... [y/N/a(lways)]: ").strip().lower()
if answer in ("a", "always"):
    add_permission(tool_name, pattern, description=detail)
    return True
```

新增 `_build_pattern()` 辅助函数：write 工具返回解析后的绝对路径，run_command 返回命令前 100 字符。

### Step 4：修改 `core/commands.py` — 新增 `/permissions`

```python
@register_command("permissions")
def cmd_permissions(engine, arg):
    """List or revoke permissions. /permissions [revoke <key>]"""
    # arg 为空 → 列出所有权限
    # arg = "revoke <key>" → 删除指定权限
```

### Step 5：修改 `main.py`

在 `build_system_prompt()` 之前调用 `init_state()`：

```python
from core.state import init_state, get_state

init_state()
engine = Engine(llm_client=llm, system_prompt=build_system_prompt(), ...)
```

---

## Phase 3.2：后台任务系统

### Step 6：创建 `core/tasks.py`

```python
MAX_CONCURRENT = 5

class TaskState(str, Enum):   # pending / running / done / failed

class Task(BaseModel):
    id: str
    command: str
    status: TaskState
    process: Any = None       # subprocess.Popen（ConfigDict arbitrary_types_allowed）
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    created_at: float
    finished_at: float
    _log_file: Any = None     # tempfile.NamedTemporaryFile，进程输出重定向目标

class TaskRunner:
    tasks: dict[str, Task]
    start(command) -> str     # Popen(stdout=logfile) + 返回 task_id
    check(task_id) -> dict    # poll + 读取 logfile 尾部，返回 {status, stdout, stderr, exit_code}
    list_all() -> list[dict]
    _reap() / _reap_one()     # 回收已完成进程，关闭临时文件

_runner: TaskRunner | None = None
get_task_runner() -> TaskRunner  # 懒初始化单例
```

**关键设计 — tempfile 实时日志（解决"黑盒"问题）：**

- `start()` 时：`log_file = tempfile.NamedTemporaryFile(delete=False, suffix=".log")`，将 `Popen(..., stdout=log_file, stderr=STDOUT)` 统一重定向到该文件。
- `check()` 时：不论进程是否完成，直接 `open(log_file_path)` 读取末尾 5000 字符（`f.seek(-5000, 2)` 或读全文），返回实时增量日志。
- `_reap_one()` 进程完成后：`os.unlink(log_file_path)` 清理临时文件。
- 效果：进程运行期间模型调用 `check_task_logs` 也能看到实时输出，不再"瞎子摸象"。

**临时文件泄漏防御（atexit 兜底）：**

`_reap_one()` 仅在进程正常结束时清理。若用户 Ctrl+C 强退或主进程崩溃，临时文件会残留。解决方案：在 `core/tasks.py` 底部注册 `atexit` 钩子：

```python
import atexit

def _cleanup_all_tasks():
    for task in get_task_runner().tasks.values():
        _cleanup_task_files(task)

atexit.register(_cleanup_all_tasks)
```

遍历所有 Task，强制关闭文件句柄并 `os.unlink()` 尚存的临时日志文件。与 main.py 的 session atexit 钩子同理。

### Step 7：创建 `tools/agent_tools.py`

薄壳，仅参数校验 + 委派：

```python
@tool("Run a command in the background. Returns a task_id.")
def run_background(command: str) -> str:
    from core.tasks import get_task_runner
    runner = get_task_runner()
    try:
        task_id = runner.start(command)
        return f"Background task started: {task_id}"
    except RuntimeError as e:
        return f"Error: {e}"

@tool("Check status and output of a background task.")
def check_task_logs(task_id: str) -> str:
    # runner.check(task_id) → 格式化为可读字符串
```

`delegate_task` 在 Phase 3.3 添加。

### Step 8：修改 `core/commands.py` — 新增 `/tasks`

```python
@register_command("tasks")
def cmd_tasks(engine, arg):
    """List background tasks and their status."""
    # TaskRunner.list_all() → 彩色状态表格
```

### Step 9：修改 `main.py` — 注册新工具

```python
import tools.agent_tools  # noqa: F401  # 注册 run_background, check_task_logs
```

---

## Phase 3.3：子代理编排器

### Step 10：修改 `core/state.py` — 添加 llm 字段

State 模型新增 `llm: AnthropicClient | None = None`（Step 1 已预留）。`main.py` 创建 llm 后赋值：

```python
get_state().llm = llm
```

### Step 11：修改 `core/llm.py` — 添加 HTTP 超时（解决"假超时"陷阱）

在 `AnthropicClient.__init__()` 中增加 `timeout` 参数，传入底层 Anthropic 客户端：

```python
def __init__(self, model="claude-sonnet-4-20250514", logger=None, timeout=60.0):
    ...
    client_kwargs["timeout"] = timeout   # Anthropic SDK 会传给 httpx
    self.client = Anthropic(**client_kwargs)
```

**效果：** 当 API 网络卡死时，`llm.send()` 会在 60s 后抛出 `APITimeoutError`，被 orchestrator 的 `except Exception` 兜底捕获，返回 `[Task Failed]`，子代理不会永久挂起。

**配合措施：** `tools/shell.py` 中 `run_command` 已有 `timeout=120`（subprocess.run 级别），确保工具执行侧也不会无限阻塞。两项物理超时组合，使 orchestrator 的循环级超时检查真正有效。

### Step 12：创建 `core/orchestrator.py`

独立 ReAct 循环，不复用 Engine.run：

```python
MAX_ITERATIONS = 30
TIMEOUT_SECONDS = 300
DEFAULT_TOOLS = ["read_file", "list_files", "glob_search", "grep_search", "run_command"]

def run_sub_agent(task_description, llm=None, allowed_tools=None) -> str:
    # 1. 构建子代理 prompt（高权重覆写指令）
    # 2. 过滤工具集（_filter_tools）
    # 3. 独立 messages = [{"role":"user","content": task_description}]
    # 4. ReAct 循环：llm.send() → tool_use → execute_tool() → 循环
    #    - 无 auto_commit
    #    - 无 HITL
    #    - 无流式输出
    #    - 迭代上限 30，超时 300s
    # 5. 异常全部捕获，返回 [Task Failed] 摘要
    # 6. KeyboardInterrupt → [Task Interrupted]
```

关键：`llm.send()` 为同步非流式调用（llm.py 中已有此方法），子代理不触发 UI 渲染。

**超时保障三重机制（解决"假超时"陷阱）：**
1. **循环级：** `while` 循环顶部的 `time.time() - start > TIMEOUT_SECONDS` 检查，覆盖正常迭代场景
2. **网络级：** `AnthropicClient` 已配置 `timeout=60s`（Step 11），API 卡死时抛 `APITimeoutError`
3. **工具级：** `run_command` 已有 `subprocess.run(timeout=120)`，工具执行不会永久阻塞

三者组合后，orchestrator 的 `except Exception` 兜底才能真正捕获各种阻塞场景，子代理不会挂起主进程。

### Step 13：在 `tools/agent_tools.py` 追加 `delegate_task`

```python
@tool("Delegate a complex sub-task to a focused sub-agent. Returns a summary.")
def delegate_task(task_description: str, tools: list[str] | None = None) -> str:
    from core.orchestrator import run_sub_agent
    result = run_sub_agent(task_description, allowed_tools=tools)
    return result[:4000] + "\n...[Truncated]" if len(result) > 4000 else result
```

**摘要截断防线（防止"爆栈"反噬）：**

子代理可能将大段代码或日志贴入返回摘要，导致主 Agent 上下文瞬间膨胀。在 `delegate_task` 薄壳中强制截断至 4000 字符。截断在工具层（而非 orchestrator 层）执行，保持 orchestrator 纯净，由薄壳承担"安全阀"职责。

---

## 实施顺序与依赖关系

```
Phase 3.1: Step 1 → Step 2 + Step 3（并行）→ Step 4 → Step 5
Phase 3.2: Step 6 → Step 7 → Step 8 + Step 9（并行）
Phase 3.3: Step 10 → Step 11 → Step 12 → Step 13
```

```
Step 1  core/state.py ──────────────────────────────┐
Step 2  core/prompts.py ← 依赖 state.py             │
Step 3  ui/hitl.py ← 依赖 state.py                  │ Phase 3.1
Step 4  core/commands.py (/permissions)              │
Step 5  main.py ← 依赖 Step 1                       │
                                                     │
Step 6  core/tasks.py ──────────────────────────────┐│
Step 7  tools/agent_tools.py ← 依赖 tasks.py        ││ Phase 3.2
Step 8  core/commands.py (/tasks) ← 依赖 tasks.py   ││
Step 9  main.py (import agent_tools)                ←┘│
                                                     │
Step 10 core/state.py (添加 llm 字段) ──────────────┐│
Step 11 core/llm.py (添加 timeout) ← 无依赖，可并行  ││ Phase 3.3
Step 12 core/orchestrator.py ← 依赖 state.llm       ││
Step 13 tools/agent_tools.py (添加 delegate_task)   ←┘┘
```

## 异常处理策略

| 边界 | 异常 | 处理方式 |
|------|------|----------|
| state.py 文件读取 | 文件缺失/损坏 | 静默返回空，不崩溃 |
| hitl.py 权限查找 | State 未初始化 | `get_state()` raise RuntimeError（正常流程不会触发） |
| tasks.py 进程启动 | OSError（命令不存在） | Task 状态设为 FAILED，stderr 记录错误 |
| tasks.py 并发超限 | 5 个任务已运行 | RuntimeError → run_background 返回 Error 字符串 |
| orchestrator API 调用 | 超时/限流/异常 | blanket `except Exception` → `[Task Failed]` |
| orchestrator 工具执行 | 工具抛异常 | `execute_tool()` 已内置 catch，返回错误字符串给子代理 |
| orchestrator 迭代超限 | > 30 次 | 返回 `[Task Failed] Max iterations reached` |
| orchestrator 超时 | > 300s | 每次循环顶部检查，返回 `[Task Failed] Timeout` |
| orchestrator Ctrl+C | KeyboardInterrupt | 返回 `[Task Interrupted]` |

## 验证方式

### Phase 3.1 验证
1. 创建 `~/.coder-rules` 写入测试规则，启动 agent 确认日志中 system prompt 包含 `<project_rules>` 块
2. 触发 HITL（如写入外部路径），选择 `a` → 确认 `~/.agentic-coder/permissions.json` 已写入
3. 重启 agent，再次触发相同操作 → 确认自动通过（无弹窗）
4. `/permissions` 查看列表，`/permissions revoke <key>` 撤销后重启验证不再自动通过

### Phase 3.2 验证
1. 让 agent 执行 `run_background("ping localhost -n 3")`，再用 `check_task_logs` 查询
2. `/tasks` 命令查看任务列表
3. 连续启动 6 个任务 → 第 6 个被拒绝

### Phase 3.3 验证
1. 让 agent 执行 `delegate_task("list all Python files", ["glob_search"])`
2. 确认子代理返回摘要文本，主会话上下文正常继续
3. 确认子代理的文件修改未触发 auto_commit
