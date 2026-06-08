# Agentic Coder - Architecture & Implementation Document

## 1. Project Overview (项目概述)

本项目旨在从零构建一个极简、强悍、高完成度的 CLI 代码智能体（对标 Claude Code）。项目基于 Anthropic 原生 API 开发，具备完整的工具调用链、本地系统控制权以及上下文无损截断能力。

核心设计哲学：
* **四层解耦:** 严格遵循 `Entry -> Engine -> Support -> Task` 的现代 Agent 架构范式。允许上层跨级读取下层数据，但绝对禁止下层反向依赖上层。
* **数据先行:** 全面采用 `Pydantic` 规范化内部数据流转，拒绝含糊不清的 Dict 传参。
* **极简克制:** 采用“回合制”状态机交替掌管终端；底层任务系统与上层决策引擎彻底分离，不写面条代码。

---

## 2. Core Architecture (四层架构模型)

系统严格按照职权边界划分为四个层级，上层依赖下层，下层对上层无感知：

1. **ENTRY LAYER (入口展现层):** 负责 I/O 与终端交互。包含 `prompt_toolkit` 多行输入、Slash 命令拦截 (`commands.py`)、`rich` 流式渲染以及 `HITL` 拦截用户的安全确认。
2. **QUERY ENGINE LAYER (中枢决策层):** 真正的“大脑”。驱动 ReAct 死循环，执行上下文压缩策略，决定下一步动作。包含纯粹的引擎类与多 Agent 调度器 (Orchestrator)。
3. **SUPPORT & STATE LAYER (支撑服务与状态层):** 包含基础设施与全局状态。提供跨层共享的工具注册表 (Registry)、API 客户端 (LLM Client)、全局状态单例 (State) 以及会话持久化服务 (Session)。
4. **TOOL & TASK SYSTEM (底层执行臂):** 严格区分为两类：
   * **Tools:** 无状态、单次阻塞调用（如 `fs.py`, `git.py`），由 LLM 通过 `tool_use` 触发。
   * **Tasks:** 有状态、长生命周期的后台进程，由 `tasks.py` 提供完整的状态机管理。

---

## 3. Project Structure (工程目录蓝图)

    agentic-coder/
    ├── core/                    # 核心大脑与基建
    │   ├── __init__.py
    │   ├── schemas.py           # [L3 Infra] Pydantic 数据模型 (AgentMessage, ToolCallReq)
    │   ├── exceptions.py        # [L3 Infra] 自定义异常
    │   ├── engine.py            # [L2 Engine] 核心引擎类 (无状态，可被实例化为主/子 Engine)
    │   ├── orchestrator.py      # [L2 Engine] 调度器 (实例化 Engine、注入权限与身份、聚合结果)
    │   ├── context.py           # [L2 Engine] 上下文压缩策略 (microcompact + auto_compact)
    │   ├── prompts.py           # [L2 Engine] System Prompt 模板与规则注入
    │   ├── state.py             # [L3 State] 全局状态单例 (.coder-rules, HITL权限记忆)
    │   ├── llm.py               # [L3 Service] Anthropic API 客户端 (流式通信)
    │   ├── session.py           # [L3 Service] 会话持久化 (JSON 序列化)
    │   ├── commands.py          # [L1 Entry] Slash 命令拦截 (/clear, /exit, /tasks)
    │   └── tasks.py             # [L4 Task] 后台进程生命周期池 (带并发上限与状态查询)
    ├── tools/                   # 动作注册与底层执行
    │   ├── __init__.py
    │   ├── registry.py          # [L3 Infra] 工具注册中心 (Pydantic 动态 Schema 生成)
    │   ├── fs.py                # [L4 Tool] 文件读写、Glob/Grep 搜索 (阻塞)
    │   ├── shell.py             # [L4 Tool] 终端基础命令执行 (阻塞)
    │   ├── git.py               # [L4 Tool] 版本控制操作 (阻塞)
    │   └── agent_tools.py       # [L4 Tool] 系统级触手“薄壳” (参数校验，委托 L2/L4 执行)
    ├── config/                  # 运行时配置
    │   ├── __init__.py
    │   └── settings.py          # .env 加载 + argparse
    ├── ui/                      # 终端展现层
    │   ├── __init__.py
    │   ├── input.py             # [L1 Entry] prompt_toolkit 输入封装
    │   ├── console.py           # [L1 Entry] rich 流式渲染 + Token 回显
    │   └── hitl.py              # [L1 Entry] 危险操作安全拦截与 Y/N/A 交互
    ├── utils/                   # 基础基建
    │   ├── __init__.py
    │   └── logger.py            # [L3 Service] 静默日志写入
    ├── .env                     # 配置文件
    ├── requirements.txt         # 项目依赖
    └── main.py                  # [L1 Entry] CLI 入口

---

## 4. Technology Stack (核心技术栈)

* **Language:** Python 3.10+
* **LLM SDK:** `anthropic`
* **Data Validation:** `pydantic`
* **Tool Registry:** `inspect` + `pydantic.create_model()`
* **CLI Input:** `prompt_toolkit`
* **CLI Output:** `rich`
* **CLI Engine:** `argparse`

---

## 5. Development Roadmap (实施路线图)

### Phase 1 & 2: 核心循环与交互升级 (已完成)
实现 ReAct 循环、多行输入、流式渲染、Glob/Grep 检索、Slash 命令与会话持久化。

### Phase 3: 架构升维与复杂任务编排 (已完成)

* **Phase 3.1: 状态层升维与动态规则 (State Layer) (已完成)**
  * **目标:** 建立 `core/state.py`，实现项目规范注入与持久化权限。
  * **实施:** 启动时按层级读取 `.coder-rules`。实现 HITL 白名单，将 `Always Allow` 写入独立配置，并在**每次系统启动时自动加载生效**。
* **Phase 3.2: 异步后台任务机制 (Task System) (已完成)**
  * **目标:** 建立 `core/tasks.py` 状态机与进程池。
  * **实施:** 引入 `@tool("run_background")`，引入 `MAX_CONCURRENT` 防爆破限制。模型显式调用 `@tool("check_task_logs")` 获取结构化输出 `{status, stdout, stderr, exit_code}`。用户侧新增 `/tasks` 命令随时透视运行中的后台进程。
* **Phase 3.3: 子代理委派系统 (Orchestrator) (已完成)**
  * **目标:** 建立 `core/orchestrator.py` 与 `@tool("delegate_task")`。
  * **实施:** 实例化独立上下文的子 Engine，配置强硬的防御性 System Prompt，**强制关闭自动 git commit 以防污染版本树**。处理子代理边界异常。

---

## 6. Key Technical Decisions (关键技术决策)

### Phase 1 & 2 决策回顾
| 决策维度 | 最终选型 | 选用原因 |
|----------|----------|----------|
| UI 交互模式 | 回合制状态机 | 隔离 prompt_toolkit 与 rich，比全屏 TUI 更轻量 |
| Schema 生成 | inspect + `create_model()` | 天然支持复杂嵌套类型，免除手动拼接 JSON |
| Git Commit | 引擎层 (engine.py) | 工具层保持纯粹，由引擎统一把控自动 commit 策略 |

### Phase 3 决策规范 (New)
| 决策维度 | 设计规范 | 细节说明 |
|----------|----------|----------|
| **工具越权隔离** | **“薄壳”模式** | `agent_tools.py` 仅作接口暴露。内部绝不包含业务逻辑，仅作参数校验后将工作委托给 `orchestrator.spawn()` 或 `tasks.spawn()`。 |
| **子代理失败策略** | **沙箱拦截与摘要** | 1. 设最大迭代防死循环；2. 崩溃或超时异常在 Orchestrator 捕获并返回 `[Task Failed]` 摘要；3. 触发 `Ctrl+C` 返回 `[Task Interrupted]`。异常绝不冒泡导致主进程崩溃。 |
| **子代理上下文** | **完全独立** | 不共享主引擎的 `messages`，仅通过 `input` 接收初始指令。结束后主引擎仅获得纯文本摘要报告。 |
| **子代理版本控制** | **静默无痕** | Orchestrator 在实例化子代理时强制注入 `auto_commit=False`，防止其在重构大模块时产生海量无意义的中间 Git Commit 污染版本树。 |
| **子代理指令冲突** | **终极覆写 (Override)** | 继承主引擎环境，并在 Prompt 末尾附加高权重的覆盖指令：`"Your ONLY goal is {task}. Do not explore beyond this scope. Return immediately when done."` |
| **后台任务防爆** | **最高并发锁** | 设定 `MAX_CONCURRENT=5`。若试图开启第 6 个进程，拒绝执行并提示模型等待或回收任务。 |
| **后台任务交互** | **模型轮询 + 用户透视** | 模型需显式调用 `check_task_logs(id)`，系统严格返回结构化数据：`{status: running/done/failed, stdout, stderr, exit_code}`，防止解析歧义。用户侧随时可通过 `/tasks` 命令强制查看状态字典。 |
| **.coder-rules** | **Markdown 合并** | 优先读取全局 `~/.coder-rules`，再读取项目 `./.coder-rules` 进行追加。通过 `<project_rules>` 标签注入主引擎 Prompt 末尾。 |
| **HITL白名单** | **独立权限文件** | 用户选择 `A (Always)` 时写入 `~/.agentic-coder/permissions.json`，系统重启自动加载生效。用户可通过手动修改 JSON 或 `/permissions` 命令撤销。（安全策略与代码规则物理隔离）。 |