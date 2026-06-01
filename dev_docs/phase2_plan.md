# Phase 2 开发计划：交互升级与能力扩充

## 总览

Phase 2 分三个子阶段，按用户感知强度和依赖关系排序：

```
Phase 2.1  交互与通信重构（输入输出痛点）
    ↓ 依赖：streaming 能力
Phase 2.2  基础能力与状态感知扩充（工具链 + Token 回显）
    ↓ 依赖：无
Phase 2.3  本地控制与会话管理（Slash 命令 + 持久化）
```

---

## Phase 2.1：交互与通信重构

### 目标

解决三个最影响体验的痛点：输入粘贴崩溃、输出等待焦虑、Ctrl+C 中断后上下文丢失。

### 涉及文件

| 文件 | 动作 | 说明 |
|------|------|------|
| `requirements.txt` | 修改 | 新增 `prompt_toolkit>=3.0.0` |
| `ui/input.py` | **新建** | prompt_toolkit 输入封装 |
| `core/llm.py` | 重构 | 新增 `send_stream()` 流式方法 |
| `ui/console.py` | 重构 | 新增 `stream_print()` 流式渲染函数 |
| `core/engine.py` | 重构 | 拆分 `run()` 为流式路径 + 中断处理 |
| `main.py` | 修改 | 接入新输入模块，替换 `input()` |

### 实施步骤

#### Step 1：prompt_toolkit 输入模块

**文件：`ui/input.py`（新建）**

```python
# 核心接口
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings

session = PromptSession()

def get_input(prompt: str = ">> ") -> str | None:
    """获取用户输入，支持多行粘贴。
    - Enter：提交
    - Shift+Enter / Alt+Enter：换行
    - Ctrl+C：返回 None（触发退出信号）
    - Ctrl+D：返回 None（EOF）
    """
```

关键设计：
- `prompt_toolkit` 完全接管 `input()`，不引入全屏 TUI 框架
- 返回 `None` 作为退出信号，`main.py` 中统一判断
- 多行输入时，`>>` 前缀替换为 `..`（续行标识）

**文件：`main.py`（修改）**

```python
# 替换 input() 为
from ui.input import get_input

while True:
    query = get_input()
    if query is None:
        break
    if query.strip().lower() in ("q", "exit", ""):
        continue
    ...
```

**验证：** `python main.py` 启动，粘贴多行代码块不崩溃，Enter 提交，Shift+Enter 换行。

---

#### Step 2：Anthropic SDK 流式调用

**文件：`core/llm.py`（重构）**

保留原 `send()` 不变（供 auto_compact 等内部调用），新增 `send_stream()` 方法：

```python
def send_stream(
    self,
    system: str,
    messages: list[dict],
    tools: list[dict] | None = None,
    max_tokens: int = 8000,
):
    """流式调用，返回 (event_stream, final_response) 二元组。

    event_stream: 迭代器，逐块产出 TextDelta / ToolUseStart / ToolUseDelta 事件
    final_response: 流结束后组装的完整 Response 对象（同 send() 返回值）
    """
```

关键设计：
- 使用 `client.messages.stream()` 上下文管理器
- 事件类型拆分：`text` delta（用于实时渲染）、`tool_use` start/delta（用于记录完整 tool call）
- 流结束后需组装 `response.content`（包含完整 `text` block 和 `tool_use` block），保持与 `send()` 返回结构一致
- **Token 计量**：Anthropic 流式 API 内置 usage 数据，无需等流结束：
  - `MessageStartEvent` 携带 `event.message.usage.input_tokens`（输入 token，流开始即知）
  - `MessageDeltaEvent` 携带 `event.usage.output_tokens`（输出 token，流结束时获得）
  - 在流式循环中捕获这两个事件，流结束后即可精确回显 token 消耗
- **中断状态追踪**：`send_stream()` 内部维护 `current_block_type`（`"text"` 或 `"tool_use"`），供调用方在 KeyboardInterrupt 时判断当前产出类型（见 Step 4）

**文件：`core/llm.py` 事件产出格式：**

```python
@dataclass
class StreamEvent:
    type: Literal["text_delta", "tool_start", "tool_delta", "done"]
    text: str = ""           # text_delta 内容
    tool_name: str = ""      # tool_start 时的工具名
    tool_id: str = ""        # tool_start 时的 tool_use_id
    tool_input_delta: str = ""  # tool_delta 累积的 JSON 片段

@dataclass
class StreamResult:
    """流结束后组装的完整结果。"""
    text: str                          # 拼接后的完整文本
    content: list                      # 同 send() 的 response.content 结构
    stop_reason: str                   # "end_turn" 或 "tool_use"
    usage: dict                        # {"input_tokens": ..., "output_tokens": ...}
    interrupted: bool = False          # 是否被 Ctrl+C 中断
    current_block_type: str = ""       # 中断时正在产出的块类型（"text" / "tool_use"）
```

**验证：** 手动调用 `send_stream()` 并打印每个 delta，确认文本逐块到达；中断后检查 `StreamResult.interrupted` 和 `current_block_type` 是否正确。

---

#### Step 3：rich.Live 流式输出渲染

**文件：`ui/console.py`（重构）**

新增 `stream_print()` 函数，封装 `rich.Live` 实现打字机动画：

```python
from rich.live import Live
from rich.markdown import Markdown

def stream_print(event_stream) -> str:
    """流式渲染，返回拼接后的完整文本。

    - 用 rich.Live 包裹 Markdown 渲染区域
    - 每收到 text_delta 就追加到缓冲区并刷新
    - tool_use 事件期间暂停 Markdown 渲染（避免 JSON 片段破坏格式）
    - 流结束后 Finalize Live（保留渲染结果在终端）
    """
```

关键设计：
- `Live` 的 `refresh_per_second=12`，平衡流畅度与 CPU 占用
- 流期间用 `Markdown(buffer)` 作为渲染对象，每个 delta 后 `live.update()`
- tool_use 事件触发时，在 Live 区域下方打印 `[dim]  calling {tool_name}...[/]`
- 流结束后 `Live` 自动停止，结果保留（`transient=False`）

**验证：** 启动 agent，观察文本逐字出现，Markdown 格式正确渲染。

---

#### Step 4：Engine 流式路径 + Ctrl+C 中断

**文件：`core/engine.py`（重构）**

```python
def run(self, user_input: str) -> str:
    self.messages.append({"role": "user", "content": user_input})
    tools = get_anthropic_tools()

    while True:
        microcompact(self.messages)
        auto_compact(self.messages, self.llm)

        try:
            result = self.llm.send_stream(
                system=self.system_prompt,
                messages=self.messages,
                tools=tools,
            )
        except KeyboardInterrupt:
            # send_stream 内部已捕获中断，正常返回 StreamResult
            pass

        # ---- 中断安全处理（核心防坑逻辑） ----
        if result.interrupted:
            safe_content = []
            if result.text:
                # 仅保留已完成的纯文本块，坚决丢弃未完成的 tool_use
                safe_content.append({"type": "text", "text": result.text})
            safe_content.append({
                "type": "text",
                "text": "\n[User interrupted the generation]"
            })
            self.messages.append({"role": "assistant", "content": safe_content})
            print_info("\n[generation interrupted]")
            break  # 回到输入循环

        # ---- 正常路径 ----
        self.messages.append({"role": "assistant", "content": result.content})

        if result.stop_reason != "tool_use":
            return result.text

        # tool 执行逻辑不变...
```

**中断安全三原则：**
1. **已完成的纯文本** → 保留到上下文（用户之前的提问 + 模型已输出的内容有连续性）
2. **未完成的 tool_use JSON** → 坚决丢弃（半截 JSON 会导致下一轮 API 请求解析崩溃）
3. **注入 `[User interrupted]` 提示** → 让模型在下一轮知道自己被强行打断，主动接续或询问

**实现细节：** `KeyboardInterrupt` 在 `send_stream()` 内部被捕获（而非在 engine.run 的 try/except 里），因为流式迭代器需要在中断时完成内部状态清理（关闭 HTTP 连接等）。`send_stream()` 返回一个 `StreamResult`，其中 `interrupted=True`，并携带中断瞬间的 `current_block_type`，engine 据此决定保留什么、丢弃什么。

**验证：**
- 模型生成纯文本时按 Ctrl+C → 上下文保留文本，再次提问能继续对话
- 模型正在输出 tool_use JSON 时按 Ctrl+C → 上下文只保留纯文本部分 + `[User interrupted]`，下一轮 API 请求不报错

---

## Phase 2.2：基础能力与状态感知扩充

### 目标

扩展工具链（Glob + Grep），增加 Token 消耗可视反馈。

### 涉及文件

| 文件 | 动作 | 说明 |
|------|------|------|
| `tools/fs.py` | 修改 | 新增 `glob_search` 和 `grep_search` 工具 |
| `ui/console.py` | 修改 | 新增 Token 回显函数 |
| `core/engine.py` | 修改 | 每轮结束调用 Token 回显 |

### 实施步骤

#### Step 1：Glob 文件搜索工具

**文件：`tools/fs.py`（新增工具）**

```python
@tool("Search for files matching a glob pattern (e.g. '**/*.py', 'src/**/*.ts').")
def glob_search(pattern: str, path: str = ".") -> str:
    """返回匹配的文件路径列表，最多 200 条。"""
```

- 使用 `pathlib.Path.glob()` 或 `glob.glob(recursive=True)`
- 默认搜索 CWD，可指定根目录
- 结果上限 200 条，避免爆 token

#### Step 2：Grep 代码搜索工具

**文件：`tools/fs.py`（新增工具）**

```python
@tool("Search file contents for a regex pattern. Returns matching lines with context.")
def grep_search(pattern: str, path: str = ".", glob: str = "*.py") -> str:
    """跨文件正则搜索，返回 file:line: 内容 格式。"""
```

- 使用 `re.finditer()` 遍历文件
- 可选 `glob` 过滤（默认 `*.py`）
- **双重截断**，防止 Token 爆炸：
  - 行数上限：100 行，超出截断并提示 `[... N more matches]`
  - **单行长度上限：200 字符**，超出截断为 `line[:200] + "..."`（防止 Webpack 压缩后的 JS 等单行巨文撑爆 Token）
- 输出格式：`path:line_number: matched_line`

#### Step 3：Token 消耗回显

**文件：`ui/console.py`（新增函数）**

```python
def print_token_usage(usage: dict) -> None:
    """暗色调打印当前轮次 Token 消耗。"""
    # 示例输出：
    # [dim]  input: 12,345 tokens | output: 890 tokens | context: 34.2%[/]
```

**文件：`core/engine.py`（修改）**

在 `run()` 方法的每次 LLM 调用后，从 `response.usage` 读取并传给 `print_token_usage()`。

---

## Phase 2.3：本地控制与会话管理

### 目标

实现 Slash 命令（本地执行，不消耗 API）和会话持久化（下次启动恢复现场）。

### 涉及文件

| 文件 | 动作 | 说明 |
|------|------|------|
| `core/commands.py` | **新建** | Slash 命令注册与分发 |
| `core/session.py` | **新建** | 会话序列化与恢复 |
| `main.py` | 修改 | 接入命令分发 + 会话加载/保存 |
| `core/engine.py` | 修改 | 暴露 `messages` 给 session 读取 |
| `ui/input.py` | 修改 | 补全 `/` 开头命令的自动提示（可选） |

### 实施步骤

#### Step 1：Slash 命令系统

**文件：`core/commands.py`（新建）**

```python
COMMANDS: dict[str, Callable] = {}

def register_command(name: str, handler: Callable):
    """注册 /name 命令"""

def handle_input(text: str, engine: Engine) -> str | None:
    """判断是否为 slash 命令，是则执行并返回 None（不进入 engine.run），
    否则原样返回 text 交给 engine。"""

# 预注册命令
@register_command("clear")
def cmd_clear(engine): engine.messages.clear()

@register_command("compact")
def cmd_compact(engine): auto_compact(engine.messages, engine.llm, threshold=0)

@register_command("exit")
def cmd_exit(engine): raise SystemExit
```

关键设计：
- 命令在 `main.py` 的输入循环里，engine.run() **之前** 拦截
- 命令直接操作 engine.messages，不经过 LLM
- 返回 `None` 表示已处理，`main.py` 继续下一轮输入

#### Step 2：会话持久化

**文件：`core/session.py`（新建）**

```python
SESSION_DIR = Path.home() / ".agentic-coder" / "sessions"

def save_session(engine: Engine, name: str = "last") -> Path:
    """序列化 engine.messages 到 JSON 文件。
    保存内容：messages 列表 + model 名称 + 时间戳
    文件格式：{name}_{timestamp}.json"""

def load_session(name: str = "last") -> dict | None:
    """加载最近一次会话，返回 {messages, model, timestamp}"""

def list_sessions() -> list[dict]:
    """列出所有已保存会话，供用户选择恢复。"""
```

**序列化说明（无需 Pydantic 参与）：**

Phase 1 中 `engine.messages` 是 `list[dict]`，不是 Pydantic 对象。所有消息均以裸 dict 形式存储（`{"role": "user", "content": ...}`），`content` 字段为 str 或 `list[dict]`，天然 JSON 可序列化。

```python
# 保存：直接 json.dump，无需 model_dump()
import json
with open(path, "w") as f:
    json.dump({"messages": engine.messages, "model": engine.llm.model}, f, ensure_ascii=False)

# 加载：直接赋值，无需 Pydantic 解析
data = json.load(f)
engine.messages = data["messages"]
```

若未来 Phase 中将 messages 重构为 Pydantic 对象，则需相应改用 `model_dump()` / `model_validate()` 进行序列化，但当前阶段不需要。

**文件：`main.py`（修改）**

```python
# 启动时
if args.resume:
    session = load_session(args.resume)
    if session:
        engine.messages = session["messages"]

# 退出时（正常退出 + Ctrl+C）
import atexit
atexit.register(lambda: save_session(engine))
```

**文件：`main.py`（argparse 新增参数）**

```python
p.add_argument("--resume", nargs="?", const="last",
               help="恢复上次会话，或指定会话名称")
```

---

## Phase 2 完整依赖关系图

```
Step 2.1.1  prompt_toolkit 输入模块（独立，无依赖）
    │
Step 2.1.2  llm.py send_stream()（独立，无依赖）
    │
Step 2.1.3  rich.Live 流式渲染 ← 依赖 2.1.2
    │
Step 2.1.4  Engine 流式路径 + Ctrl+C ← 依赖 2.1.1 + 2.1.3
    │
    ├── Step 2.2.1  Glob 工具（独立）
    ├── Step 2.2.2  Grep 工具（独立）
    ├── Step 2.2.3  Token 回显 ← 依赖 2.1.2（需要 response.usage）
    │
    ├── Step 2.3.1  Slash 命令（独立）
    └── Step 2.3.2  会话持久化（独立）
```

---

## 新增依赖

```
# requirements.txt（Phase 2 新增）
prompt_toolkit>=3.0.0
```

无其他外部依赖，Glob/Grep/Session 全部用标准库实现。
