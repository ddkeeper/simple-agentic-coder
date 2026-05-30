# CLAUDE.md

## Project Overview

构建一个完整的 CLI 编程 Agent（类 Claude Code），先实现核心功能并跑通测试，再拆解为多步教学教程。

## 当前阶段

**阶段一：实现完整 Agent**（已完成）
目标：实现所有核心模块，形成可用的 CLI 编程工具。

阶段二（后续）：将完整代码拆解为 10 章渐进式教程。

## 项目结构

```
agentic-coder/
├── core/
│   ├── __init__.py
│   ├── schemas.py           # Pydantic 数据模型
│   ├── exceptions.py        # 自定义异常
│   ├── engine.py            # ReAct 主循环 + context 压缩 + HITL
│   ├── llm.py               # Anthropic SDK 封装（同步非流式，支持 base_url）
│   ├── context.py           # microcompact + auto_compact + token 估算
│   └── prompts.py           # System Prompt 模板（动态注入环境信息）
├── tools/
│   ├── __init__.py
│   ├── registry.py          # @tool 装饰器 + inspect + Pydantic 动态 Schema 生成
│   ├── fs.py                # read_file / write_file / edit_file / list_files
│   ├── shell.py             # run_command（subprocess，120s 超时，危险命令拦截）
│   └── git.py               # git_log + get_current_branch
├── config/
│   ├── __init__.py
│   └── settings.py          # .env 加载 + argparse
├── ui/
│   ├── __init__.py
│   ├── console.py           # rich.Console 颜色打印
│   └── hitl.py              # HITL 审批：外部路径写入 + 危险命令确认
├── utils/
│   ├── __init__.py
│   └── logger.py            # 静默日志写入 (~/.agentic-coder/logs/)
├── .env                     # API Key, Model ID, Base URL
├── requirements.txt
└── main.py                  # CLI 入口，组装组件启动 REPL
```

## 安全模型

采用 HITL（Human-in-the-Loop）审批机制，不做硬路径沙箱：

- `read_file` / `list_files`：任何路径均允许，不需确认
- `write_file` / `edit_file`：CWD 内允许；CWD 外弹出 `Approve? [y/N]` 确认
- `run_command`：匹配危险模式（`rm -rf`、`sudo` 等）时弹出确认
- `--yes` 参数可跳过所有确认（自动批准）

## 核心功能清单

1. **Agent Loop** — `while stop_reason == "tool_use"` 循环
2. **Tool Dispatch** — `@tool` 装饰器 + `inspect` + `pydantic.create_model()` 自动 Schema 生成
3. **System Prompt** — 动态注入 cwd、OS、日期、git 分支、项目文件树（前 20 条）
4. **HITL 安全审批** — 外部路径写入 / 危险命令需用户确认
5. **Context Compaction** — microcompact（清理旧 tool_result）+ LLM 摘要压缩（40k token 阈值）
6. **多 Provider 支持** — 通过 ANTHROPIC_BASE_URL 切换 MiniMax / GLM / Kimi / DeepSeek 等
8. **静默日志** — 完整请求/响应记录到 JSONL 文件，API key 自动脱敏

## Running

```bash
cd agentic-coder
pip install -r requirements.txt
# 编辑 .env 填入 API Key 和模型 ID
python main.py

# 自动批准所有工具调用
python main.py --yes

# 指定模型
python main.py --model deepseek-chat
```

## Conventions

- Python 3.10+（使用 `str | None` 联合类型语法）
- 核心循环不变性：`engine.py` 中的 `while` 循环是所有功能的承载点
- 权限策略在 HITL 层（`ui/hitl.py`），工具层保持纯净
- 工具通过 `registry.execute_tool()` 统一分发，不直接调用
