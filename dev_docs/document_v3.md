# Agentic Coder - Architecture & Implementation Document

## 1. Project Overview (项目概述)

本项目旨在从零构建一个极简、强悍、高完成度的 CLI 代码智能体（对标 Claude Code）。项目基于 Anthropic 原生 API 开发，具备完整的工具调用链、本地系统控制权以及上下文无损截断能力。

核心设计哲学：
* **四层解耦:** 严格遵循 `Entry -> Engine -> Support -> Task` 的现代 Agent 四层架构范式。
* **数据先行:** 全面采用 `Pydantic` 规范化内部数据流转，拒绝含糊不清的 Dict 传参。
* **极简克制:** 采用“回合制”状态机交替掌管终端；底层任务系统与上层决策引擎彻底分离，不写面条代码。

---

## 2. Core Architecture (四层架构模型)

系统严格按照职权边界划分为四个层级，上层依赖下层，下层对上层无感知：

1. **ENTRY LAYER (入口展现层):** 负责 I/O 与终端交互。由 `prompt_toolkit` 处理多行输入，`rich` 处理流式打字机渲染，以及 `HITL` 拦截用户的安全确认。
2. **QUERY ENGINE LAYER (中枢决策层):** 真正的“大脑”。驱动 ReAct 死循环，组装 System Prompt，执行上下文压缩策略，决定下一步动作。它不直接干活，只负责调度。
3. **SUPPORT & STATE LAYER (支撑服务与状态层):** 为决策层提供资源库。包含：工具注册中心 (Registry)、全局状态 (AppState/Rules)、API 通信客户端 (LLM Client)、本地会话持久化服务 (Session)。
4. **TASK & EXECUTION SYSTEM (物理任务层):** 底层执行臂。包含单次阻塞的物理工具（读写文件、Git 操作）以及长耗时后台任务的生命周期管理器（进程池）。

---

## 3. Project Structure (工程目录蓝图)

```text
agentic-coder/
├── core/                    # [Layer 2 & 3] 核心中枢与支撑服务
│   ├── __init__.py
│   ├── schemas.py           # [L3 Data] Pydantic 数据模型 (AgentMessage, ToolCallReq)
│   ├── exceptions.py        # [L3 Data] 自定义异常
│   ├── engine.py            # [L2 Engine] 主/子 Agent 循环 (ReAct + git auto-commit)
│   ├── orchestrator.py      # [L2 Engine] (待建) 多 Agent 调度器，负责派生子引擎
│   ├── context.py           # [L2 Engine] 上下文压缩策略 (microcompact + auto_compact)
│   ├── prompts.py           # [L2 Engine] System Prompt 模板组装
│   ├── llm.py               # [L3 Service] Anthropic API 客户端 (封装流式通信)
│   ├── state.py             # [L3 State] (待建) 全局状态单例 (.coder-rules, HITL白名单)
│   ├── session.py           # [L3 Service] 会话持久化 (JSON 序列化)
│   ├── commands.py          # [L3 Service] Slash 命令分发机制
│   └── tasks.py             # [L4 Task] (待建) 后台进程生命周期管理池
├── tools/                   # [L3/L4] 动作注册与底层执行
│   ├── __init__.py
│   ├── registry.py          # [L3 Service] 工具注册中心 (Pydantic 动态 Schema 生成)
│   ├── fs.py                # [L4 Task] 文件读写、Glob/Grep 搜索
│   ├── shell.py             # [L4 Task] 终端命令执行
│   ├── git.py               # [L4 Task] 版本控制操作
│   └── agent_tools.py       # [L4 Task] (待建) 系统级钩子 (如 run_background)
├── config/                  # 运行时配置
│   ├── __init__.py
│   └── settings.py          # .env 加载 + argparse
├── ui/                      # [Layer 1] 终端展现层
│   ├── __init__.py
│   ├── input.py             # prompt_toolkit 输入封装
│   ├── console.py           # rich 流式渲染 + Token 回显
│   └── hitl.py              # 危险操作安全拦截
├── utils/                   # 基础基建
│   ├── __init__.py
│   └── logger.py            # [L3 Service] 静默日志写入
├── .env                     # 配置文件
├── requirements.txt         # 项目依赖
└── main.py                  # [Layer 1] CLI 入口