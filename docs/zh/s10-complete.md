# s10: Complete

> **核心洞察**: 把 9 个章节的单文件 agent 拆成工程结构——教学代码到生产代码的最后一步。

## 到此为止你有了什么

一个完整的 coding agent，具备：

| 功能 | 来源章节 |
|-----|---------|
| Agent loop | s01 |
| 工具分发 | s02 |
| System prompt | s03 |
| 任务规划 | s04 |
| 子代理 | s05 |
| 上下文压缩 | s06 |
| 权限系统 | s07 |
| Git 集成 | s08 |
| 后台任务 | s09 |

## 工程结构

从单文件拆分为模块：

```
final/
├── __main__.py         # CLI 入口
├── loop.py             # agent loop 核心（~60行）
├── tools/
│   ├── __init__.py     # TOOLS 列表 + TOOL_HANDLERS
│   ├── bash.py         # bash + 后台任务
│   ├── files.py        # read / write / edit / find
│   ├── todo.py         # TodoManager
│   ├── task.py         # subagent
│   └── git.py          # 自动 commit
├── permissions.py      # 权限分级
├── compaction.py       # context 压缩
└── config.py           # CLI 参数 + 环境变量
```

## 模块间关系

```
__main__.py
    |
    v
loop.py  ─────────────────────┐
    |                          |
    +---> tools/bash.py        |
    +---> tools/files.py       |
    +---> tools/todo.py        |  被 loop 调用
    +---> tools/task.py        |
    +---> tools/git.py         |
    |                          |
    +---> permissions.py ──────┘
    +---> compaction.py
    +---> config.py
```

`loop.py` 是中心，其他模块都是它调用的工具或策略。

## s01 → s10 的演变

```
s01:  80行，一个文件，一个工具
s02:  +120行，dispatch map
s03:  +30行，system prompt
s04:  +80行，TodoManager
s05:  +60行，task 工具
s06:  +50行，compact
s07:  +40行，permission
s08:  +50行，git
s09:  +60行，background
s10:  拆分为 10 个文件，每个 <100 行
```

## 与生产级 agent 的差距

这个 agent 已经涵盖了 Claude Code 80% 的核心机制，但还有一些生产级功能我们刻意省略了：

| 省略的功能 | 为什么省略 |
|-----------|-----------|
| Hook 系统 | 事件钩子，非核心循环组件 |
| MCP Server | 外部工具协议，架构层面是"工具"的扩展 |
| Memory 文件 | 持久化记忆，简单文件读写 |
| Cron Scheduler | 定时任务，独立于 agent loop |
| Streaming | 流式输出，用户体验优化而非架构问题 |
| 多模型支持 | 模型切换是配置问题，不是架构问题 |

这些功能可以在核心架构理解之后再逐一添加。

## 试一试

```bash
python -m final
```

推荐 prompt：

1. `Create a Python project with a main module and utility functions`
2. `Add tests using pytest, run them in the background, and fix any failures`
3. `Refactor the project: move utility functions into a separate package`
4. `Review all files, check git log, and summarize what we built`
