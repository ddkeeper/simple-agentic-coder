# Simple Agentic Coder

从零构建一个类 Claude Code 的 AI 编程 Agent。

10 个章节，每章一个可运行的 Python 文件，从最简单的 agent loop 开始，逐步叠加工具、规划、子代理、上下文压缩、权限系统、Git 集成、后台任务，最终得到一个功能完整但代码精简的 coding agent。

## 项目结构

```
simple-agentic-coder/
├── agents/                    # 每章一个独立可运行文件
│   ├── s01_agent_loop.py      # 核心循环 + bash 工具
│   ├── s02_tool_dispatch.py   # 工具分发 + 路径沙箱
│   ├── s03_system_prompt.py   # 系统提示设计
│   ├── s04_todo_write.py      # 任务规划 + nag reminder
│   ├── s05_subagent.py        # 子代理 + 上下文隔离
│   ├── s06_context_compact.py # 消息压缩
│   ├── s07_permission.py      # 权限系统
│   ├── s08_git_integration.py # Git 自动提交
│   ├── s09_background.py      # 后台任务
│   └── s10_complete.py        # 完整版
├── final/                     # 模块化工程版本
│   ├── __main__.py
│   ├── loop.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── bash.py
│   │   ├── files.py
│   │   ├── todo.py
│   │   ├── task.py
│   │   └── git.py
│   ├── permissions.py
│   ├── compaction.py
│   └── config.py
├── docs/
│   ├── zh/                    # 中文教学文档
│   └── en/                    # 英文教学文档
└── requirements.txt
```

## 快速开始

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="your-key-here"

# 从第一章开始
python agents/s01_agent_loop.py
```

## 教学路线

| 章节 | 主题 | 一句话说明 |
|------|------|-----------|
| s01 | Agent Loop | `while tool_use` — 一个循环 + bash = 一个 agent |
| s02 | Tool Dispatch | 加工具不改循环，注册到 dispatch map 就行 |
| s03 | System Prompt | 好的 prompt 是 agent 的灵魂 |
| s04 | TodoWrite | 先列计划再动手，nag reminder 制造问责压力 |
| s05 | Subagent | 独立上下文处理子任务，父 agent 保持清醒 |
| s06 | Context Compact | 对话太长时自动压缩，守住 context window |
| s07 | Permission | 工具分级：auto / ask / deny |
| s08 | Git Integration | 每次改动自动 diff + commit |
| s09 | Background Tasks | 耗时任务丢后台，主循环不阻塞 |
| s10 | Complete | 整合所有模块，拆分成工程结构 |

## 学完你会理解

- Agent 的本质就是 `while stop_reason == "tool_use"` 这一个循环
- 工具是函数，dispatch map 是字典，没有什么魔法
- Context window 管理是生产级 agent 最核心的工程问题
- 权限系统如何在"自主性"和"安全性"之间取得平衡
- 一个 Claude Code / Cursor / Aider 背后真正的架构骨架长什么样

## 参考项目

- [learn-claude-code](https://github.com/anthropics/learn-claude-code) — 本项目的教学结构直接参考此项目
- [aider](https://github.com/paul-gauthier/aider) — 理解 LLM 驱动的另一种 agent 设计：策略模式 + diff 格式
