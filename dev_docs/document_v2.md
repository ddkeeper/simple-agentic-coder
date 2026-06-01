# Agentic Coder - Architecture & Implementation Document

## 1. Project Overview (项目概述)

本项目旨在从零构建一个极简、强悍、高完成度的 CLI 代码智能体（对标 Claude Code）。项目基于 Anthropic 原生 API 开发，具备完整的工具调用链、本地系统控制权以及上下文无损截断能力。

核心设计哲学：
* **高度解耦:** 坚决将底层运转逻辑（LLM API、路由、状态机）与表现层（CLI UI）分离。
* **数据先行:** 全面采用 `Pydantic` 规范化内部数据流转，拒绝含糊不清的 Dict 传参。
* **极简克制:** 采用“回合制”状态机架构，严格隔离输入状态（prompt_toolkit）与输出状态（rich），避免引入臃肿的全屏 TUI 框架；终端 UI 拒绝花哨，只保留必要的颜色区分；底层日志脱离 UI，静默写入文件供开发者排障。

---

## 2. Core Architecture (核心架构)

系统采用经典的 ReAct (Reason + Act) 循环控制流。架构划分为五个高内聚子系统：

1. **Brain (核心引擎):** 包含 `Engine` 状态机与 `LLMClient`，驱动核心的思考与分发逻辑。
2. **Tools (执行臂):** 插件化注册机制，动态生成 Anthropic Tool Schema；包含文件精确操作、终端命令执行和 Git 基础管理工具。
3. **Context (上下文):** 负责维护当前工作区的全局状态，执行 microcompact (微压缩) 和 auto_compact (大模型摘要压缩)，防止多轮对话爆 Token。
4. **Interface (交互层):** 基于“回合制”交替掌管终端。输入时由 `prompt_toolkit` 提供多行粘贴与光标控制，输出时由 `rich` 提供打字机流式渲染。
5. **Guard (安全护盾):** Human-in-the-Loop (HITL) 拦截机制，强制高危操作在终端挂起等待二次确认。

---

## 3. Project Structure (工程目录蓝图)

agentic-coder/
├── core/                    # 核心大脑与中枢
│   ├── __init__.py
│   ├── schemas.py           # Pydantic 数据模型 (AgentMessage, ToolCallReq, ToolResult)
│   ├── exceptions.py        # 自定义异常 (ToolExecutionError, ContextLimitError)
│   ├── engine.py            # Agent 主循环 (ReAct 流式路径 + 中断安全处理 + git auto-commit)
│   ├── llm.py               # Anthropic SDK 封装 (send 同步 + send_stream 流式 Generator)
│   ├── context.py           # microcompact + auto_compact + token 估算
│   ├── commands.py          # Slash 命令注册与分发 (/clear, /compact, /exit, /help, /resume, /sessions)
│   ├── session.py           # 会话持久化 (save/load/list，JSON 序列化到 ~/.agentic-coder/sessions/)
│   └── prompts.py           # System Prompt 模板 (动态注入环境信息)
├── tools/                   # 动作执行层
│   ├── __init__.py
│   ├── registry.py          # 工具注册中心 (inspect + Pydantic 动态 Schema 生成)
│   ├── fs.py                # 文件操作 (read/write/edit/list/glob_search/grep_search)
│   ├── shell.py             # 终端执行 (subprocess，120s 超时，危险命令拦截)
│   └── git.py               # git log / git commit / get_branch 工具
├── config/                  # 运行时配置
│   ├── __init__.py
│   └── settings.py          # .env 加载 + argparse
├── ui/                      # 终端展现层
│   ├── __init__.py
│   ├── input.py             # prompt_toolkit 输入封装 (多行粘贴、Alt+Enter 换行、Ctrl+C 退出)
│   ├── console.py           # rich.Console + stream_print 流式渲染 + print_token_usage + print_session_history
│   └── hitl.py              # input("Approve? [y/N]") 最简安全拦截实现
├── utils/                   # 基础基建
│   ├── __init__.py
│   └── logger.py            # 静默日志写入 (~/.agentic-coder/logs/)
├── test/                    # 自动化测试 + 人工测试指南
│   ├── test_phase2_auto.py        # Phase 2.1/2.2 自动化测试 (离线 + 真实 API)
│   ├── test_phase2_manual.md      # Phase 2.1/2.2 人工对话测试指南
│   ├── test_phase2_3_auto.py      # Phase 2.3 自动化测试 (离线，命令 + 会话)
│   └── test_phase2_3_manual.md    # Phase 2.3 人工测试指南
├── .env                     # 配置文件 (API Key, Model ID, Base URL)
├── requirements.txt         # 项目依赖
└── main.py                  # CLI 入口 (会话管理 + 实时自动保存 + Slash 命令分发)

---

## 4. Technology Stack (核心技术栈)

* **Language:** Python 3.10+
* **LLM SDK:** `anthropic` (原生支持 Messages API 与 Tool Use，支持 base_url 切换)
* **Data Validation:** `pydantic` (严格校验内部实体状态)
* **Tool Registry:** 通过 `inspect` 获取函数签名，动态调用 `pydantic.create_model()` 生成参数模型，再通过 `.model_json_schema()` 输出 Anthropic 兼容的 Schema。
* **CLI Input:** `prompt_toolkit` (专职负责多行输入拦截、复杂粘贴行为与光标管理)
* **CLI Output:** `rich` (专职负责多行渲染、Markdown 语法高亮与打字机流式输出)
* **CLI Engine:** `argparse` (标准库，零依赖)

---

## 5. Development Roadmap (实施路线图)

### Phase 1: 核心主循环打通 (已完成)

严格遵循“基建先行，UI 殿后”的开发顺序，实现单核死循环：
* **Step 1: schemas.py + exceptions.py** -> 确立 Pydantic 数据地基与核心异常。
* **Step 2: llm.py + logger.py** -> 封装同步非流式 API 调用，建立静默日志。
* **Step 3: registry.py + fs.py** -> 实现动态 Schema 生成器，挂载基础文件读写。
* **Step 4: engine.py + main.py + shell.py** -> 激活核心 ReAct 循环，赋予 Agent 终端命令执行与自我修复能力。

### Phase 2: 交互升级与能力扩充 (已完成)

优化用户感知最强的交互细节，逐步从小玩具走向真正的生产力工具：

* **Phase 2.1: 交互与通信重构 (解决输入输出痛点)** ✅
  * **多行输入拦截:** 引入 `prompt_toolkit` 接管原生 `input()`，彻底解决多行错误日志、代码块粘贴崩溃的痛点。`ui/input.py` 封装了 `PromptSession`，Enter 提交、Alt+Enter 换行、Ctrl+C/D 返回退出信号。
  * **流式输出 (Streaming):** `core/llm.py` 新增 `send_stream()` Generator 方法，使用 `client.messages.stream()` 上下文管理器，通过双 yield 模式（先 yield StreamContext，再 yield StreamEvent）解耦 LLM 客户端、Console 渲染器和 Engine 三方。`ui/console.py` 的 `stream_print()` 消费 Generator，用 `rich.Live` + `Markdown` 实现打字机渲染。
  * **优雅中断 (Ctrl+C):** `KeyboardInterrupt` 在 Generator 内部捕获（保证 HTTP 连接关闭），Engine 侧做防御性二次捕获：保留已完成的纯文本 block，丢弃未完成的 tool_use JSON（防止下轮 API 解析崩溃），注入 `[User interrupted]` 标记。

* **Phase 2.2: 基础能力与状态感知扩充 (增强工具链)** ✅
  * **Glob 文件搜索:** `tools/fs.py` 新增 `glob_search(pattern, path)` 工具，基于 `Path.glob()`，结果上限 200 条。
  * **Grep 代码搜索:** 新增 `grep_search(pattern, path, glob)` 工具，使用 `re` 模块跨文件正则搜索，双重截断（行数上限 100 + 单行长度 200 字符），跳过超大文件。
  * **Token 消耗回显:** `ui/console.py` 新增 `print_token_usage()`，每轮对话结束后显示累计 input/output token 数（`turn_usage` 在 engine.run 的多次 LLM 调用间累加，仅在回合结束时打印一次）。

* **Phase 2.3: 本地控制与会话管理 (走向成熟雏形)** ✅
  * **Slash 命令系统:** `core/commands.py` 实现命令注册/分发机制，`main.py` 输入循环中在 `engine.run()` 之前拦截。内置命令：`/clear` (清空上下文)、`/compact` (强制摘要压缩)、`/exit` (退出)、`/help` (帮助)、`/resume` (切换会话)、`/sessions` (列出会话)。
  * **会话持久化:** `core/session.py` 实现 JSON 序列化（自动处理 Anthropic SDK 对象如 ThinkingBlock/TextBlock/ToolUseBlock 转纯 dict）。实时保存：每次 `engine.run()` 返回后自动保存；atexit 兜底安全网。新会话以时间戳命名（`session_YYYYMMDD_HHMMSS`），恢复的会话覆盖原名。`--resume` 不带参数恢复最近会话，`/resume` 运行中切换会话时清屏并显示目标会话历史。

### Phase 3: 进阶功能探索 (下一目标)

* **Subagent (子代理):** 支持派生独立上下文、工具权限受限的子任务智能体，完成复杂长链任务拆解。
* **Background Tasks (后台任务):** 配合线程与生命周期机制，允许 Agent 在后台静默运行长耗时测试命令而不阻塞主交互循环。
* **MCP 协议集成:** 接入 Model Context Protocol，打通更广泛的外部生态工具。

---

## 6. Key Technical Decisions (关键技术决策)

| 决策维度 | 最终选型 | 选用原因 |
|----------|----------|----------|
| UI 交互模式 | 回合制状态机 (Turn-based) | 严格隔离输入（prompt_toolkit）与输出（rich）状态，比全屏 TUI 框架（Textual）更轻量、线性、可控 |
| Schema 生成 | inspect + Pydantic `create_model()` | 天然支持 Union/Optional 及复杂嵌套类型，完全免除手动拼接 JSON 的边缘 case |
| Git Commit 位置 | 引擎层 (engine.py) | 工具层（fs.py）应保持纯粹，由引擎层统一把控文件修改成功后的自动 commit 策略，便于后续子代理权限隔离 |
| 安全审批模型 | HITL 拦截机制 | 不采用强路径沙箱隔离，不限制生产工具的路径自由度，将控制权完全交给用户的 Y/N 互动确认 |