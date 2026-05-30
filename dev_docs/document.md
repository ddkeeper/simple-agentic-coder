# Agentic Coder - Architecture & Implementation Document

## 1. Project Overview (项目概述)

本项目旨在从零构建一个极简、强悍、高完成度的 CLI 代码智能体（对标 Claude Code）。项目基于 Anthropic 原生 API 开发，具备完整的工具调用链、本地系统控制权以及上下文无损截断能力。

核心设计哲学：
* **高度解耦:** 坚决将底层运转逻辑（LLM API、路由、状态机）与表现层（CLI UI）分离。
* **数据先行:** 全面采用 `Pydantic` 规范化内部数据流转，拒绝含糊不清的 Dict 传参。
* **极简克制:** 砍掉冗余动画，终端 UI 拒绝花哨，只保留必要的颜色区分；底层日志脱离 UI，静默写入文件供开发者溯源。

---

## 2. Core Architecture (核心架构)

系统采用经典的 ReAct (Reason + Act) 循环控制流。架构划分为五个高内聚子系统：

1. **Brain (核心引擎):** 包含 `Engine` 状态机与 `LLMClient`。
2. **Tools (执行臂):** 插件化注册，通过 `inspect` + Pydantic `create_model()` 动态生成 Anthropic Tool Schema；包含纯粹的文件操作、终端执行和 Git 查询工具。
3. **Context (上下文):** 负责维护当前工作区的全局状态，执行 microcompact (微压缩) 和 auto_compact (大模型摘要压缩)，防止多轮对话爆 Token。
4. **Interface (交互层):** 极简的终端 UI 控制台与输入拦截。
5. **Guard (安全护盾):** Human-in-the-Loop (HITL) 拦截机制，强制高危操作在终端挂起等待确认。

---

## 3. Project Structure (工程目录蓝图)

```
agentic-coder/
├── core/                    # 核心大脑与中枢
│   ├── __init__.py
│   ├── schemas.py           # Pydantic 数据模型 (AgentMessage, ToolCallReq, ToolResult)
│   ├── exceptions.py        # 自定义异常 (ToolExecutionError, ContextLimitError)
│   ├── engine.py            # Agent 主循环 + context 压缩 + HITL
│   ├── llm.py               # Anthropic SDK 封装（同步非流式，支持 base_url）
│   ├── context.py           # microcompact + auto_compact + token 估算
│   └── prompts.py           # System Prompt 模板（动态注入环境信息）
├── tools/                   # 动作执行层
│   ├── __init__.py
│   ├── registry.py          # 工具注册中心 (inspect + Pydantic 动态 Schema 生成)
│   ├── fs.py                # 文件操作 (read/write/edit/list，任意路径，HITL 控制写入)
│   ├── shell.py             # 终端执行 (subprocess，120s 超时，危险命令拦截)
│   └── git.py               # git log / get_branch（auto-commit 留 Phase 2）
├── config/                  # 运行时配置
│   ├── __init__.py
│   └── settings.py          # .env 加载 + argparse
├── ui/                      # 终端展现层
│   ├── __init__.py
│   ├── console.py           # 全局 rich.Console + 颜色打印
│   └── hitl.py              # 危险操作 Y/N 拦截
├── utils/                   # 基础基建
│   ├── __init__.py
│   └── logger.py            # 静默日志写入 (~/.agentic-coder/logs/)
├── .env                     # 配置文件 (API Key, Model ID, Base URL)
├── requirements.txt         # 项目依赖
└── main.py                  # CLI 入口，组装组件并启动 REPL
```

---

## 4. Technology Stack (核心技术栈)

* **Language:** Python 3.10+
* **LLM SDK:** `anthropic` (原生支持 Messages API 与 Tool Use，支持 base_url 切换)
* **Data Validation:** `pydantic` (严格校验内部实体状态)
* **Tool Registry:** 通过 `inspect` 获取函数签名，动态调用 `pydantic.create_model()` 生成参数模型，再通过 `.model_json_schema()` 输出 Anthropic 兼容的 Schema，天然支持 Union、Optional、嵌套类型。
* **CLI Engine:** `argparse` (标准库，零依赖)
* **Terminal UI:** `rich` (极简控制台打印)

---

## 5. Configuration (配置说明)

在 `agentic-coder/.env` 中配置：

```bash
# 必填：API Key
ANTHROPIC_API_KEY=your-api-key-here

# 必填：模型 ID
MODEL_ID=claude-sonnet-4-20250514

# 可选：第三方兼容端点
# ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
```

支持的第三方兼容端点：

| Provider | MODEL_ID | Base URL |
|----------|----------|----------|
| Anthropic | claude-sonnet-4-6 | (默认) |
| MiniMax | MiniMax-M2.5 | https://api.minimax.io/anthropic |
| GLM (Zhipu) | glm-5 | https://api.z.ai/api/anthropic |
| Kimi (Moonshot) | kimi-k2.5 | https://api.moonshot.ai/anthropic |
| DeepSeek | deepseek-chat | https://api.deepseek.com/anthropic |

中国大陆用户可使用对应的 `.cn` 域名端点。

---

## 6. Development Roadmap (实施路线图)

### Phase 1 (已完成)

严格遵循"基建先行，UI 殿后"的开发顺序，每个阶段皆可独立测试：

* **Step 1: schemas.py + exceptions.py** (Pydantic 数据地基)
  定义 `AgentMessage`, `ToolCallRequest`, `ToolResult`, `AgentConfig` 等内部流转实体。

* **Step 2: llm.py + logger.py** (API 通信与静默日志)
  `AnthropicClient` 封装同步 API 调用，支持 `ANTHROPIC_BASE_URL` 切换；`Logger` 静默记录完整请求/响应到 JSONL 文件。

* **Step 3: registry.py + fs.py** (工具注册与验证)
  `@tool` 装饰器通过 `inspect` + `pydantic.create_model()` 自动生成 Anthropic Tool Schema；完成 4 个文件操作工具，读操作任意路径自由访问，写操作标记 `dangerous=True` 由 HITL 控制。

* **Step 4: engine.py + main.py + shell.py** (激活 ReAct 主循环)
  核心跳动：`while stop_reason == "tool_use"` 循环，工具通过 `registry.execute_tool()` 统一分发，`try/except` 包裹防止崩溃。

* **Step 5: context.py** (上下文压缩)
  `microcompact` 清理 3 轮前的陈旧 tool_result（保留 read_file）；`auto_compact` 在 token 超 40k 时触发 LLM 摘要压缩。

* **Step 6: git.py** (Git 基础工具)
  `git_log` 查看提交历史，`get_current_branch` 获取分支名供 system prompt 注入。git auto-commit 与 rewind 功能留待 Phase 2 实现。

* **Step 7: console.py + hitl.py + prompts.py** (UI 皮肤与安全阀)
  `rich.Console` 颜色区分；危险操作 `input("Approve? [y/N]")` 拦截；system prompt 动态注入 cwd、OS、日期、git 分支、项目文件树。

### Phase 2 (规划中)

* Git Auto-commit + Rewind（版本回退）：写文件后自动 commit，支持 `git reset --hard` 回退到任意历史节点
* Subagent（子代理）：独立上下文的子任务执行
* Background Tasks（后台任务）：长时间运行的命令不阻塞主循环
* .coder-rules（项目规则）：项目级自定义规则注入
* Streaming（流式输出）：`client.messages.stream()` 逐字输出
* Memory（持久记忆）：跨会话的知识保留

---

## 7. Running (启动方式)

```bash
cd agentic-coder
pip install -r requirements.txt
# 编辑 .env 填入你的 API Key 和模型 ID
python main.py

# 自动批准所有工具调用（适合信任环境）
python main.py --yes

# 指定模型
python main.py --model deepseek-chat
```

---

## 8. Key Technical Decisions (关键技术决策)

| 决策 | 选择 | 原因 |
|------|------|------|
| Schema 生成 | inspect + Pydantic `create_model()` | 天然支持 Union/Optional/嵌套，不手写 JSON |
| 安全模型 | HITL 审批而非硬路径沙箱 | 生产工具不限制路径，外部写入由用户确认 |
| microcompact 策略 | 替换内容为占位符，不删消息 | 保持 user/assistant 交替结构 |
| system prompt 文件树 | 仅顶层 20 条 | 避免每次 API 调用浪费 token |
| CLI 框架 | argparse | 标准库零依赖，MVP 够用 |
| git auto-commit | Phase 2 与 rewind 一起实现 | 单独做无意义，配合版本回退才有价值 |
| 流式输出 | Phase 1 不做 | 同步阻塞最简单，streaming 留 Phase 2 |
