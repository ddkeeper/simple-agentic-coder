# Phase 2.3 人工测试指南：Slash 命令 + 会话持久化

启动方式：
```bash
cd agentic-coder
python main.py
```

---

## 1. Slash 命令基础

测试目标：所有内置命令能正常执行，不消耗 API token。

### 1.1 /help 命令

```
>> /help
```

预期：显示所有可用命令列表（/clear, /compact, /exit, /help, /resume, /sessions），格式清晰，每个命令附带一行说明。不调用 LLM，无 token 消耗。

### 1.2 /clear 命令

先正常对话一轮：
```
>> What is Python?
```

然后清除上下文：
```
>> /clear
```

预期：显示 `conversation cleared`。再次提问验证上下文已清空：
```
>> What was my previous question?
```

预期：模型表示不知道（因为上下文被清除了）。

### 1.3 /exit 命令

```
>> /exit
```

预期：程序正常退出，无报错。效果等同于输入 `q` 或 `exit`。

### 1.4 未知命令

```
>> /foobar
```

预期：显示错误提示 `Unknown command: /foobar. Type /help for available commands.`，不崩溃，回到 `>>`。

### 1.5 /compact 命令

```
>> /compact
```

预期：触发强制上下文压缩（如果上下文较小，显示 `nothing to compact`；如果较大，显示压缩信息）。

---

## 2. 会话持久化

测试目标：会话实时保存、恢复、列出。

### 2.1 实时自动保存

启动并进行一轮对话：
```
>> Remember the number 9999. Just say OK.
```

预期：模型回答后，会话立即自动保存到 `~/.agentic-coder/sessions/session_YYYYMMDD_HHMMSS.json`（时间戳命名）。

验证：
```bash
ls ~/.agentic-coder/sessions/
```
应看到新创建的时间戳命名的会话文件。

### 2.2 恢复最近会话（--resume）

紧接 2.1，退出后重新启动：
```bash
python main.py --resume
```

预期：
1. 先显示 Banner：`Agentic Coder (model_name)`
2. 显示 `session resumed: session_xxx, 2 messages`
3. 显示历史对话内容（用户消息 + 模型回答）
4. 提问验证上下文：
```
>> What number did I ask you to remember?
```
预期：模型回答 9999。

### 2.3 恢复指定会话（--resume name）

```bash
python main.py --resume session_20260601_155754
```

预期：加载指定名称的会话，显示历史内容。如果名称不存在，显示 `session 'xxx' not found, starting fresh`。

### 2.4 /sessions 命令（列出所有会话）

```
>> /sessions
```

预期：显示所有已保存会话列表，每行包含：名称、消息数量、模型名、保存时间。按时间倒序（最新在前）。

### 2.5 /resume 命令（运行中切换会话）

先对话几轮建立上下文，然后：
```
>> /resume session_20260601_155754
```

预期：
1. 当前会话自动保存（未命名则用时间戳，已有名则更新原名）
2. 显示 `current session auto-saved as 'session_xxx'`
3. 加载目标会话，显示其历史内容
4. 后续对话基于目标会话的上下文继续

### 2.6 /resume 不带参数（恢复最近会话）

```
>> /resume
```

预期：效果同 `--resume`，加载最近一次保存的会话并显示历史。

### 2.7 恢复不存在的会话

```
>> /resume nonexistent_session
```

预期：显示 `session 'nonexistent_session' not found`，不崩溃，当前会话不受影响。

### 2.8 每次回答后实时保存

启动，问多个问题：
```
>> What is 1+1?
>> What is 2+2?
>> What is 3+3?
```

每次回答后检查会话文件是否更新：
```bash
# 多次执行，观察 timestamp 和 message_count 递增
cat ~/.agentic-coder/sessions/session_*.json | python -c "import sys,json; d=json.load(sys.stdin); print(d['message_count'], d['timestamp'])"
```

预期：每轮回答后文件都被更新，message_count 递增。

---

## 3. 综合场景

### A. 命令 + 正常对话交替

```
>> What is Python?
>> /clear
>> What is JavaScript?
>> /sessions
>> /help
>> /exit
```

预期：每条命令正确执行，对话和命令交替不影响彼此。退出时会话自动保存。

### B. 多会话切换

1. 启动：`python main.py`
2. 对话：`>> Hello, remember AAA=111`
3. 退出：`>> q`
4. 再启动新会话：`python main.py`
5. 对话：`>> Hello, remember BBB=222`
6. 退出：`>> q`
7. 重启恢复最近：`python main.py --resume`
8. 验证只记得 BBB=222
9. 切换到第一个：`>> /resume` 找到第一个会话
10. 验证只记得 AAA=111

预期：两个会话独立，切换不互相污染，切换后显示对应历史。

### C. 中断 + 会话恢复

1. 启动，问一个需要长回答的问题
2. 在输出过程中按 Ctrl+C 中断
3. 退出
4. 用 `--resume` 恢复
5. 验证中断前的上下文（包括 `[User interrupted]` 标记）被保留

预期：中断的内容被正确保存，恢复后上下文完整。

---

## 4. 检查点（快速验证清单）

| # | 检查项 | 命令/操作 | 预期结果 |
|---|--------|-----------|----------|
| 1 | /help 显示 | `>> /help` | 显示 6 个命令 |
| 2 | /clear 清空 | `>> /clear` | 消息数归零，提示已清空 |
| 3 | /exit 退出 | `>> /exit` | 程序正常退出 |
| 4 | 未知命令 | `>> /xyz` | 错误提示，不崩溃 |
| 5 | 实时保存 | 对话后检查 sessions/ | 时间戳文件已创建/更新 |
| 6 | --resume 最近 | `python main.py --resume` | 恢复最近会话，显示历史 |
| 7 | --resume 指定 | `python main.py --resume xxx` | 恢复指定会话 |
| 8 | /resume 切换 | `>> /resume xxx` | 当前自动保存 + 加载目标 + 显示历史 |
| 9 | /sessions 列表 | `>> /sessions` | 显示所有会话 |
| 10 | 恢复不存在 | `>> /resume nope` | 提示不存在，不崩溃 |
