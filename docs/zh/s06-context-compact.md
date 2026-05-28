# s06: Context Compact

> **核心洞察**: context window 是有限资源，agent 最大的工程问题不是能力，是记忆管理。

## 问题

Agent 工作 20 轮后，messages 可能有 50000+ tokens。大量是中间工具输出——已经用完了、不会再用，但依然占着位置。要么上下文爆掉，要么 LLM 因为 token 太多开始"忘记"系统提示的规则。

## 解决方案

当 messages 超过阈值时，用 LLM 自己压缩旧消息为摘要，替换掉原始内容。

```
Before compact:
  [sys] [user_1] [asst_1] [user_2] [asst_2] ... [user_20] [asst_20]
  |<--- 这些是旧的，可以压缩 --->|

After compact:
  [sys] [summary_of_rounds_1_to_15] [user_16] ... [user_20] [asst_20]
        |<--- 一次 LLM 调用得到的摘要 --->|
```

## 工作原理

1. 在 agent loop 中检查 token 数量。

```python
def estimate_tokens(messages):
    text = json.dumps(messages)
    return len(text) // 4  # 粗略估计
```

2. 超过阈值时，截取旧消息调用 LLM 生成摘要。

```python
def compact_messages(messages, keep_recent=6):
    old = messages[:-keep_recent]
    recent = messages[-keep_recent:]
    summary_prompt = [{
        "role": "user",
        "content": f"Summarize this conversation in 200 words:\n{json.dumps(old)}"
    }]
    summary = client.messages.create(
        model=MODEL, messages=summary_prompt, max_tokens=500
    )
    compacted = [{"role": "user", "content": f"[Conversation summary]\n{summary}"}]
    return compacted + recent
```

3. 系统提示不压缩，始终保持完整。

## 压缩策略选择

| 策略 | 优点 | 缺点 |
|-----|------|------|
| 滑动窗口 | 简单、确定性 | 丢失早期信息 |
| LLM 摘要 | 保留语义 | 额外 API 调用、摘要可能遗漏细节 |
| 混合 | 两者平衡 | 实现稍复杂 |

本实现采用 LLM 摘要，因为这是 Claude Code 的实际策略，也是最值得理解的一种。

## 相对 s05 的变更

| 组件         | s05            | s06                           |
|-------------|----------------|-------------------------------|
| 消息管理      | 无限增长       | 超阈值自动 compact             |
| Agent loop  | 不变           | + compact 检查逻辑             |
| 新增函数      | 无             | `compact_messages()`          |

## 试一试

```bash
python agents/s06_context_compact.py
```

推荐 prompt（连续多轮对话，触发压缩）：

1. `Create a file called data.txt with 100 lines of random text`
2. `Read the file and tell me what's on line 50`
3. `Edit line 50 to say "modified by agent"`
4. `Now create 5 more files with different content`
5. `Read all 6 files and give me a summary of each` — 这里应该触发 compact
