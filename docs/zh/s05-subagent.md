# s05: Subagent

> **核心洞察**: 大任务拆小，每个子任务用干净的上下文，父 agent 保持清醒。

## 问题

Agent 工作越久，messages 数组越臃肿。每次读文件、跑命令的输出都永久留在上下文里。"这个项目用什么测试框架？"可能要读 5 个文件，但父 agent 只需要一个词："pytest"。

## 解决方案

```
Parent agent                     Subagent
+------------------+             +------------------+
| messages=[...]   |             | messages=[]      | <-- fresh
|                  |  dispatch   |                  |
| tool: task       | ----------> | while tool_use:  |
|   prompt="..."   |             |   call tools     |
|                  |  summary    |   append results |
|   result = "..." | <---------- | return last text |
+------------------+             +------------------+

Parent context stays clean. Subagent context is discarded.
```

## 工作原理

1. 父 agent 有一个 `task` 工具。子代理拥有除 `task` 外的所有基础工具（禁止递归生成）。

```python
PARENT_TOOLS = CHILD_TOOLS + [
    {"name": "task",
     "description": "Spawn a subagent with fresh context.",
     "input_schema": {
         "type": "object",
         "properties": {"prompt": {"type": "string"}},
         "required": ["prompt"],
     }},
]
```

2. `task` handler 创建全新的 messages 数组，调用同一个 agent_loop。

```python
def run_task(prompt: str) -> str:
    child_messages = [{"role": "user", "content": prompt}]
    agent_loop(child_messages, tools=CHILD_TOOLS)
    # Return only the last assistant text
    last = child_messages[-1]["content"]
    if isinstance(last, list):
        texts = [b.text for b in last if hasattr(b, "text")]
        return "\n".join(texts) if texts else "(no output)"
    return str(last)
```

3. 子代理的上下文在返回后丢弃，父 agent 只拿到摘要。

## 关键约束

- 子代理不能再生成子代理（`task` 工具不传给子代理）
- 子代理返回的是纯文本摘要，不是完整消息历史
- 子代理看不到父 agent 的 messages，是完全隔离的

## 相对 s04 的变更

| 组件         | s04            | s05                              |
|-------------|----------------|----------------------------------|
| Tools       | 6              | 6 + task（父）/ 5（子）           |
| 上下文模型    | 单一 messages  | 父子分离，子上下文丢弃            |
| Agent loop  | 不变           | 同一个函数，不同 tools 列表       |

## 试一试

```bash
python agents/s05_subagent.py
```

推荐 prompt：

1. `Analyze this project structure — what files exist and what do they do?`
2. `Find the test file and check what testing framework it uses`
3. `Create a utility module, then create tests for it — use subtasks`
