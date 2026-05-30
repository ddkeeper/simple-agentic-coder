# Agentic Coder 项目分析报告

> 生成日期：2026-05-30

---

## 一、项目概述

**Agentic Coder** 是一个基于 ReAct（Reasoning + Acting）模式的 **AI 编码代理**。它通过 Anthropic 兼容的 LLM API（如 Claude、MiniMax、GLM、Kimi、DeepSeek 等）驱动，实现一个自主循环的编码助手：接收用户指令 → LLM 推理 → 调用工具执行操作 → 将结果反馈给 LLM → 继续推理，直到任务完成。

核心特点：
- **工具驱动**：LLM 通过函数调用（Tool Use）直接操控文件系统、Shell 命令、Git
- **人机协作（HITL）**：危险操作需要用户确认
- **上下文压缩**：自动管理超长对话上下文，防止 token 溢出
- **多模型兼容**：通过 `ANTHROPIC_BASE_URL` 可接入多家兼容 Provider
- **自动提交**：文件修改后自动 Git commit，保留完整变更历史

---

## 二、目录结构

```
agentic-coder/
├── .env                    # 环境配置（API Key、Model、Base URL）
├── main.py                 # CLI 入口，初始化并启动交互循环
├── requirements.txt        # Python 依赖（anthropic、python-dotenv）
│
├── config/                 # 配置模块
│   ├── __init__.py
│   └── settings.py         # 运行时配置：argparse + dotenv 加载
│
├── core/                   # 核心引擎模块
│   ├── __init__.py
│   ├── engine.py           # ReAct Agent 循环主引擎
│   ├── llm.py              # Anthropic API 客户端封装
│   ├── prompts.py          # 系统提示词构建器（动态注入环境上下文）
│   ├── context.py          # 上下文窗口管理（microcompact + auto_compact）
│   ├── schemas.py          # Pydantic 数据模型定义
│   └── exceptions.py       # 自定义异常
│
├── tools/                  # 工具注册与实现
│   ├── __init__.py
│   ├── registry.py         # 工具注册中心（自动从函数签名生成 JSON Schema）
│   ├── fs.py               # 文件系统工具（read_file、write_file、edit_file、list_files）
│   ├── shell.py            # Shell 命令执行工具（run_command）
│   └── git.py              # Git 工具（git_log、git_auto_commit、get_current_branch）
│
├── ui/                     # 用户界面模块
│   ├── __init__.py
│   ├── console.py          # Rich 终端彩色输出
│   └── hitl.py             # Human-in-the-Loop 审批逻辑
│
├── utils/                  # 工具类
│   ├── __init__.py
│   └── logger.py           # 静默文件日志（JSONL 格式，自动脱敏）
│
└── dev_docs/               # 开发文档目录
    └── project_analysis.md # 本分析报告
```

---

## 三、核心模块功能说明

### 3.1 `main.py` — CLI 入口

负责：
1. 加载 `.env` 环境变量
2. 解析命令行参数（`--model`、`--yes`）
3. 导入并注册所有工具（`tools.fs`、`tools.shell`、`tools.git`）
4. 初始化 LLM 客户端和 Engine
5. 启动 REPL 交互循环，接收用户输入，调用 `engine.run()`

```python
# 关键流程
import tools.fs       # 注册文件工具
import tools.shell    # 注册 Shell 工具
import tools.git      # 注册 Git 工具
engine = Engine(llm_client=llm, system_prompt=..., auto_approve=args.yes)
while True:
    query = input(">> ")
    result = engine.run(query)
    print_assistant(result)
```

### 3.2 `core/engine.py` — ReAct Agent 引擎

这是整个系统的核心循环，实现了经典的 **ReAct 模式**：

```
┌─────────────────────────────────────────────┐
│              ReAct Agent Loop               │
│                                             │
│  1. 用户输入 → 加入 messages                │
│  2. microcompact() 压缩旧 tool_result       │
│  3. auto_compact() 超长时 LLM 摘要压缩      │
│  4. LLM.send() 调用大模型                    │
│  5. 如果 stop_reason != "tool_use" → 返回   │
│  6. 遍历 tool_use block：                    │
│     a. HITL 审批检查                         │
│     b. execute_tool() 执行工具               │
│     c. 写操作后 git_auto_commit()            │
│     d. 打印工具执行结果                      │
│  7. tool_results 加入 messages → 回到步骤 2  │
└─────────────────────────────────────────────┘
```

关键设计：
- `self.messages` 维护完整对话历史（含 tool_result）
- 每次 LLM 调用前执行上下文压缩，防止 token 超限
- 工具执行失败不会崩溃，而是将错误信息返回给 LLM 让其自行处理
- 写操作（`write_file`/`edit_file`）后自动 Git 提交

### 3.3 `core/llm.py` — LLM 客户端

封装 Anthropic SDK，支持：
- 自定义 `base_url` 接入兼容 Provider（MiniMax、GLM、Kimi、DeepSeek 等）
- 绕过系统代理（`proxy=None, trust_env=False`），解决 SSL 问题
- 清除 `ANTHROPIC_AUTH_TOKEN` 环境变量，避免代理软件（Clash/V2Ray）注入干扰
- 同步非流式调用，`max_tokens=8000`
- 内置 Logger 记录请求/响应详情

### 3.4 `core/prompts.py` — 系统提示词构建器

动态注入以下上下文信息到系统提示词：
- 工作目录路径
- 操作系统类型
- 当前日期
- Git 当前分支
- 项目文件列表（最多 20 个）
- 能力声明（读写文件、执行命令、查看 Git 历史）
- 行为规则（直接行动、验证工作、不编造内容）

### 3.5 `core/context.py` — 上下文管理

实现两级上下文压缩策略：

| 策略 | 触发条件 | 方式 | 保留策略 |
|------|----------|------|----------|
| **microcompact** | 每次 LLM 调用前 | 清除旧 tool_result 的内容，替换为 `[cleared by microcompact]` | 保留最近 3 轮（6 条消息）；保留 `read_file` 结果 |
| **auto_compact** | token 数 > 40000 | 用 LLM 将旧消息摘要为 300 字以内的总结 | 保留最近 6 条消息 |

`estimate_tokens()` 通过 `len(json) / 4` 粗略估算 token 数。

### 3.6 `tools/registry.py` — 工具注册中心

核心机制：使用 Python 装饰器 `@tool()` 自动注册函数为 Agent 工具。

工作原理：
1. `@tool("描述")` 装饰器读取函数签名（参数名、类型注解、默认值）
2. 通过 Pydantic `create_model()` 动态生成 JSON Schema
3. 注册到全局 `TOOL_REGISTRY` 字典
4. `get_anthropic_tools()` 导出为 Anthropic API 所需的 `tools` 格式
5. `execute_tool()` 根据名称查找并执行对应函数

额外特性：
- `dangerous=True` 标记危险工具（需要 HITL 确认）
- 异常捕获，返回错误信息而非崩溃

### 3.7 `tools/fs.py` — 文件系统工具

| 工具 | 功能 | 危险等级 |
|------|------|----------|
| `read_file(path, limit)` | 读取文件内容，支持限制行数，上限 50000 字符 | 安全 |
| `write_file(path, content)` | 写入文件，自动创建目录 | **危险** |
| `edit_file(path, old_text, new_text)` | 替换文件中首次出现的文本 | **危险** |
| `list_files(path)` | 列出目录内容，最多 100 条，区分目录/文件 | 安全 |

### 3.8 `tools/shell.py` — Shell 工具

`run_command(command)`：
- 使用 `subprocess.run(shell=True)` 执行
- 内置危险命令黑名单拦截（`rm -rf /`、`sudo`、`shutdown` 等）
- 120 秒超时保护
- 输出截断为 50000 字符

### 3.9 `tools/git.py` — Git 工具

| 函数 | 用途 | 是否为 @tool |
|------|------|-------------|
| `git_log(count)` | 显示最近 N 条 commit | ✅ 是（LLM 可调用） |
| `git_auto_commit(filepath, msg)` | 自动暂存并提交单个文件 | ❌ 否（Engine 内部调用） |
| `get_current_branch()` | 获取当前分支名 | ❌ 否（prompt 构建时调用） |

### 3.10 `ui/hitl.py` — 人机协作审批

审批策略：

| 场景 | 行为 |
|------|------|
| 写操作路径在 CWD 内 | ✅ 自动放行 |
| 写操作路径在 CWD 外 | ⚠️ 弹出确认 |
| Shell 命令包含危险模式 | ⚠️ 弹出确认 |
| `--yes` 模式 | ✅ 跳过所有确认 |
| 只读操作（read/list） | ✅ 始终放行 |

### 3.11 `utils/logger.py` — 日志系统

- JSONL 格式写入 `~/.agentic-coder/logs/` 目录
- 自动脱敏：正则替换 API Key（`sk-ant-*`、`sk-*`）
- 记录所有 LLM 请求/响应的元数据（模型、token 用量、stop_reason 等）

### 3.12 `core/schemas.py` — 数据模型

使用 Pydantic 定义核心数据结构：
- `ToolCallRequest` — LLM 的工具调用请求
- `ToolResult` — 工具执行结果
- `TextBlock` — 文本消息块
- `AgentMessage` — 对话消息（user/assistant）
- `AgentConfig` — 运行时配置

### 3.13 `core/exceptions.py` — 自定义异常

- `ToolExecutionError` — 工具执行失败
- `ContextLimitError` — 上下文超限且压缩失败

---

## 四、完整工作流程

### 4.1 启动流程

```
main.py
  │
  ├─ load_dotenv(.env)           # 加载环境变量
  ├─ parse_args()                 # 解析命令行参数
  ├─ import tools.fs              # 注册文件系统工具
  ├─ import tools.shell           # 注册 Shell 工具
  ├─ import tools.git             # 注册 Git 工具
  ├─ AnthropicClient(model)       # 初始化 LLM 客户端
  ├─ build_system_prompt()        # 构建系统提示词
  │    ├─ 获取 CWD、OS、日期、Git 分支
  │    └─ 列出项目文件
  ├─ Engine(llm, prompt, approve) # 初始化 Agent 引擎
  └─ REPL 循环                    # 等待用户输入
```

### 4.2 单轮交互流程

```
用户输入 "帮我创建一个 hello.py"
  │
  ▼
Engine.run(user_input)
  │
  ├─ 1. messages.append({role: "user", content: user_input})
  │
  ├─ 2. microcompact(messages)          # 清理旧 tool_result
  │
  ├─ 3. auto_compact(messages, llm)     # 超长时摘要压缩
  │
  ├─ 4. llm.send(system, messages, tools)  # 调用 LLM
  │     │
  │     ▼
  │    Anthropic API → 返回 response
  │    （可能包含 text + tool_use blocks）
  │
  ├─ 5. messages.append({role: "assistant", content: response.content})
  │
  ├─ 6. 检查 stop_reason
  │     ├─ ≠ "tool_use" → return final_text（结束循环）
  │     └─ = "tool_use" → 继续步骤 7
  │
  ├─ 7. 遍历 tool_use blocks:
  │     │
  │     ├─ check_approval(name, input)    # HITL 审批
  │     │    ├─ 自动放行 → continue
  │     │    └─ 需要确认 → 弹出 y/N
  │     │         ├─ y → continue
  │     │         └─ N → 返回 "User denied"
  │     │
  │     ├─ execute_tool(name, input)      # 执行工具
  │     │    └─ TOOL_REGISTRY[name].func(**input)
  │     │
  │     ├─ 如果是 write_file/edit_file:
  │     │    └─ git_auto_commit(path, msg)  # 自动提交
  │     │
  │     └─ print_tool(name, output)       # 打印结果
  │
  ├─ 8. messages.append({role: "user", content: [tool_results...]})
  │
  └─ 9. 回到步骤 2（继续循环）
```

### 4.3 上下文压缩流程

```
每次 LLM 调用前:
  │
  ├─ microcompact(messages)
  │    ├─ 找到 cutoff = len(messages) - 6
  │    ├─ 遍历旧消息中的 tool_result blocks
  │    ├─ 保留 read_file 结果（模型可能还要引用）
  │    └─ 其余 >100 字符的 tool_result → "[cleared by microcompact]"
  │
  └─ auto_compact(messages, llm)
       ├─ estimate_tokens(messages) > 40000 ?
       │    ├─ 否 → 跳过
       │    └─ 是 ↓
       ├─ 分离 old（旧消息）和 recent（最近 6 条）
       ├─ 用 LLM 生成 old 的摘要（<300 字）
       ├─ messages.clear()
       ├─ messages.append({summary})
       └─ messages.extend(recent)
```

---

## 五、技术栈

| 组件 | 技术 |
|------|------|
| LLM SDK | `anthropic` (Anthropic Python SDK) |
| 配置管理 | `python-dotenv` + `.env` 文件 |
| 数据模型 | `pydantic` (v2) |
| HTTP 客户端 | `httpx`（绕过系统代理） |
| 终端 UI | `rich` |
| 版本控制 | `gitpython`（可选） |
| 日志 | 自定义 JSONL Logger |

---

## 六、架构亮点

1. **装饰器驱动的工具系统**：`@tool()` 装饰器自动从函数签名生成 Anthropic Tool Schema，开发者只需关注业务逻辑，无需手动编写 JSON Schema。

2. **两级上下文压缩**：
   - **Microcompact**（零成本）：直接清除旧 tool_result 内容
   - **Auto-compact**（LLM 调用）：超长时生成语义摘要
   - 两级策略平衡了性能与上下文保留

3. **无状态 Engine 设计**：`Engine` 只维护 `self.messages` 一个状态，所有模块通过依赖注入连接，便于测试和扩展。

4. **安全多层防护**：
   - 工具层面：`DANGEROUS_PATTERNS` 拦截危险 Shell 命令
   - 审批层面：HITL 确认外部路径写入和危险命令
   - 代理层面：绕过系统代理避免中间人风险
   - 日志层面：API Key 自动脱敏

5. **多模型兼容**：通过 `.env` 中的 `ANTHROPIC_BASE_URL` 和 `MODEL_ID` 切换不同 Provider，无需修改代码。

---

## 七、扩展建议

1. **流式输出**：当前为同步非流式调用，可升级为 streaming 以改善用户体验
2. **并行工具调用**：当前按顺序执行 tool_use blocks，可改为并行
3. **持久化对话**：支持保存/加载会话历史
4. **权限分级**：更细粒度的工具权限控制（如只读模式、沙箱模式）
5. **Web UI**：可基于 Gradio/Streamlit 构建 Web 界面替代终端
6. **插件系统**：支持用户自定义工具，无需修改核心代码

---

*报告完毕。*
