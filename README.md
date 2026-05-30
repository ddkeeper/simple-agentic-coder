# Simple Agentic Coder

一个完整的 CLI 编程 Agent 实现，参考 Claude Code 的核心架构设计。基于 Anthropic Messages API 的 Tool Use 功能，采用 ReAct 循环架构。

## 项目目标

先实现一个功能完整的 CLI 编程工具（阶段一），跑通测试后再拆解为多步教学教程（阶段二）。

## 核心功能

| 功能 | 说明 |
|------|------|
| Agent Loop | `while stop_reason == "tool_use"` 核心循环 |
| Tool Dispatch | `@tool` 装饰器 + inspect + Pydantic 自动 Schema 生成 |
| System Prompt | 动态注入 cwd、OS、日期、git 分支、项目文件树 |
| HITL 安全审批 | 外部路径写入 / 危险命令需用户确认 |
| Context Compaction | microcompact + LLM 摘要压缩（40k token 阈值） |
| 多 Provider 支持 | 通过 ANTHROPIC_BASE_URL 切换 MiniMax / GLM / Kimi / DeepSeek |
| 静默日志 | 完整请求/响应写入 JSONL，API key 自动脱敏 |

## 项目结构

```
agentic-coder/
├── core/
│   ├── schemas.py           # Pydantic 数据模型
│   ├── exceptions.py        # 自定义异常
│   ├── engine.py            # ReAct 主循环 + context 压缩 + HITL
│   ├── llm.py               # Anthropic SDK 封装（支持 base_url）
│   ├── context.py           # microcompact + auto_compact
│   └── prompts.py           # System Prompt 动态模板
├── tools/
│   ├── registry.py          # 工具注册中心（自动 Schema 生成）
│   ├── fs.py                # read_file / write_file / edit_file / list_files
│   ├── shell.py             # run_command（120s 超时，危险命令拦截）
│   └── git.py               # git_log + get_current_branch
├── config/
│   └── settings.py          # .env + argparse
├── ui/
│   ├── console.py           # rich.Console 颜色打印
│   └── hitl.py              # HITL 审批（外部路径写入 + 危险命令确认）
├── utils/
│   └── logger.py            # JSONL 日志
├── .env                     # API Key, Model ID, Base URL
├── requirements.txt
└── main.py                  # CLI 入口 + REPL
```

## 快速开始

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

## 支持的 LLM Provider

| Provider | MODEL_ID | Base URL |
|----------|----------|----------|
| Anthropic | claude-sonnet-4-6 | （默认） |
| MiniMax | MiniMax-M2.5 | https://api.minimax.io/anthropic |
| GLM (Zhipu) | glm-5 | https://api.z.ai/api/anthropic |
| Kimi (Moonshot) | kimi-k2.5 | https://api.moonshot.ai/anthropic |
| DeepSeek | deepseek-chat | https://api.deepseek.com/anthropic |

中国大陆用户可使用对应 `.cn` 域名端点。

## 技术栈

- Python 3.10+
- anthropic（Messages API + Tool Use）
- pydantic（数据校验 + 动态 Schema 生成）
- rich（终端颜色）
- python-dotenv
