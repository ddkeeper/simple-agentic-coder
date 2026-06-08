# Phase 3 人工测试指南：State Layer + Task System + Orchestrator

启动方式：
```bash
cd agentic-coder
python main.py
```

---

## 1. Coder Rules 注入

测试目标：`.coder-rules` 文件内容被注入到系统提示中。

### 1.1 创建全局 coder-rules

```bash
echo "Always use type hints in Python code." > ~/.coder-rules # 当前用户主目录下
```

启动 agent：
```
python main.py
>> What rules do you follow?
```

预期：模型回答中提到 "type hints" 相关规则（因为该规则已被注入系统提示）。

### 1.2 创建项目级 coder-rules

在项目目录下创建：
```bash
echo "Never use print statements. Use logging instead." > .coder-rules
```

重启 agent：
```
python main.py
>> What rules do you follow?
```

预期：模型同时提到全局规则（type hints）和项目规则（no print statements），因为两者会被合并注入。

### 1.3 清理

```bash
rm ~/.coder-rules .coder-rules
```

---

## 2. HITL 权限持久化

测试目标："Always Allow" 选择被持久化，重启后自动生效。

**前置条件：** 确保 `C:/temp` 目录存在，且**不使用 `--yes` 启动**。

### 2.1 触发 HITL 并选择 Always

启动 agent：
```
python main.py
>> Use write_file to write the text "hello" to the absolute path C:/temp/test_permissions.txt. Do NOT use a relative path.
```

> **注意：** 必须明确要求 agent 使用绝对路径 `C:/temp/...`。如果 agent 使用相对路径（如 `test_permissions.txt`），文件会写入 CWD 内部，不会触发 HITL。

当终端出现黄色提示时：
```
  Approve? Write to external path: C:/temp/test_permissions.txt [y/N/a(lways)]:
```
输入 `a`（不是 `y`，只有 `a` 才会保存权限）。

预期：
1. 文件被写入
2. 权限文件已创建在 `C:\Users\intangible\.agentic-coder\permissions.json`

验证：
```bash
cat C:/Users/intangible/.agentic-coder/permissions.json
```
应看到包含 `write_file:C:\temp\test_permissions.txt` 的 JSON。

### 2.2 重启验证自动通过

重启 agent：
```
python main.py
>> Use write_file to overwrite C:/temp/test_permissions.txt with the text "world"
```

预期：不再弹出 HITL 确认，直接写入文件。

### 2.3 /permissions 命令

```
>> /permissions
```

预期：显示已保存的权限列表，包含 tool_name:pattern 和描述。

### 2.4 /permissions revoke

```
>> /permissions revoke write_file:C:/temp/test_permissions.txt
```

预期：显示 `Revoked: write_file:C:/temp/test_permissions.txt`。

验证：
```
>> /permissions
```
预期：显示 `No saved permissions.`

### 2.5 清理

```bash
rm ~/.agentic-coder/permissions.json
rm C:/temp/test_permissions.txt
```

---

## 3. 后台任务系统

测试目标：run_background 启动后台任务，check_task_logs 可查看实时日志。

### 3.1 启动后台任务

```
>> Run this in the background: python -u -c "import time; [print(f'line {i}') or time.sleep(1) for i in range(5)]"
```

预期：模型调用 `run_background`，返回 `Background task started: task_X`。

### 3.2 查询运行中的任务日志

```
>> Check the logs of the background task
```

预期：模型调用 `check_task_logs`，返回部分输出（如 `line 0`、`line 0\nline 1` 等，取决于时机）。状态为 `running`。

### 3.3 等待完成后再次查询

等待几秒后：
```
>> Check the task logs again
```

预期：状态变为 `done`，exit_code=0，完整输出所有 5 行。

### 3.4 /tasks 命令

```
>> /tasks
```

预期：显示所有后台任务列表，包含 task_id、状态（绿色 done / 黄色 running / 红色 failed）、命令预览、exit code。

### 3.5 并发限制测试

```
>> Start 5 background tasks running "python -u -c 'import time; time.sleep(30)'"
>> Now start one more background task
```

预期：第 6 个任务被拒绝，返回 `Max 5 concurrent tasks reached` 错误。

---

## 4. 子代理委派

测试目标：delegate_task 创建隔离子代理，返回摘要，不影响主上下文。

### 4.1 简单委派任务

```
>> Use delegate_task to list all Python files in the current directory. Pass tools=["glob_search"].
```

预期：
1. 模型调用 `delegate_task("...", ["glob_search"])`
2. 子代理在后台静默执行（终端无输出）
3. 返回工具结果，包含 `.py` 文件列表
4. 主会话上下文正常继续

### 4.2 验证上下文隔离

```
>> What was the exact task I gave to the sub-agent?
```

预期：模型能回答（因为它记录了 delegate_task 的调用参数），但子代理的内部对话不会出现在主上下文中。

### 4.3 验证无 auto_commit

```
>> Use delegate_task to create a file called /tmp/subagent_test.txt with content "hello from sub-agent". Pass tools=["write_file"].
```

预期：文件被创建，但没有 git commit（因为子代理的 auto_commit 被禁用）。

验证：
```bash
git log --oneline -3
# 应该没有 "write_file: /tmp/subagent_test.txt" 的 commit
cat /tmp/subagent_test.txt
# 应该显示 "hello from sub-agent"
```

### 4.4 委派失败隔离

如果子代理任务失败（如无效工具），返回 `[Task Failed] ...` 错误信息，主会话不崩溃。

---

## 5. 综合场景

### A. 完整工作流

```
python main.py
>> What rules do you follow?                    # 验证 coder-rules 注入
>> /permissions                                  # 查看权限列表（应为空）
>> Write "test" to C:/temp/test.txt             # 触发 HITL，选 a
>> /permissions                                  # 验证新权限已保存
>> Run "echo done" in background                # 启动后台任务
>> /tasks                                        # 查看任务状态
>> Use delegate_task to list all .md files      # 委派子代理
>> /permissions revoke write_file:C:/temp/test.txt  # 撤销权限
>> /permissions                                  # 验证已撤销
>> q                                             # 退出
```

预期：所有命令和工具调用正常工作，无崩溃。

### B. 权限 + 后台任务 + 子代理同时运行

1. 启动 2 个后台任务
2. 委派一个子代理执行搜索任务
3. 子代理执行期间调用 `/tasks` 查看后台任务状态
4. 全部完成后验证输出

预期：三者独立运行，互不干扰。

---

## 6. 检查点（快速验证清单）

| # | 检查项 | 命令/操作 | 预期结果 |
|---|--------|-----------|----------|
| 1 | coder-rules 注入 | 创建 ~/.coder-rules 后提问 | 模型遵循规则 |
| 2 | 权限 Always Allow | HITL 时选 a | permissions.json 已写入 |
| 3 | 权限持久化 | 重启后再次触发相同操作 | 自动通过，无弹窗 |
| 4 | /permissions 列表 | `>> /permissions` | 显示权限列表 |
| 5 | /permissions 撤销 | `>> /permissions revoke <key>` | 权限被删除 |
| 6 | 后台任务启动 | `>> Run "echo 1" in background` | 返回 task_id |
| 7 | 实时日志 | 任务运行中 check_task_logs | 可见部分输出 |
| 8 | /tasks 列表 | `>> /tasks` | 显示所有任务状态 |
| 9 | 并发限制 | 启动 6 个任务 | 第 6 个被拒绝 |
| 10 | 子代理委派 | `delegate_task(...)` | 返回摘要 |
| 11 | 上下文隔离 | 子代理的内部对话 | 不出现在主上下文 |
| 12 | 无 auto_commit | 子代理写文件 | 无 git commit |
