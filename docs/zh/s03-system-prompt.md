# s03: System Prompt

> **核心洞察**: 好的 system prompt 是 agent 的灵魂——它决定 agent 的行为边界。

## 问题

s02 的 agent 有了工具，但行为不可控：可能输出冗长解释、忘记工作目录、不遵守代码风格。没有好的 prompt，能力再强也用不好。

## 解决方案

system prompt 是注入每轮对话的角色设定，决定 agent "是谁"、"能做什么"、"怎么做"。

```python
SYSTEM = """You are a coding agent working in {cwd}.

## Capabilities
- Read, write, edit files
- Run shell commands
- Find files by name pattern

## Rules
- Act, don't explain. Make changes directly.
- Use tools to verify your work (read after edit).
- Keep working until the task is fully complete.
- Never fabricate file contents — always read first.
"""
```

## 工作原理

1. 动态注入上下文信息（工作目录、操作系统、时间）。

```python
system = SYSTEM.format(
    cwd=os.getcwd(),
    platform=platform.system(),
    date=datetime.now().strftime("%Y-%m-%d"),
)
```

2. Prompt 分层：角色 > 规则 > 上下文 > 输出格式。

```python
SYSTEM = """
{role}              # 你是谁
{rules}             # 你应该怎么做
{context}           # 当前环境信息
{output_format}     # 输出格式要求
"""
```

3. 保持 prompt 简洁。每增加一条规则都要验证它是否真的有效——无效规则只会稀释有效指令的注意力。

## 为什么不用中文 prompt

默认使用英文 prompt，原因是：
- 主流 LLM 的英文指令跟随能力更强
- 英文 token 效率更高（同样的意思消耗更少 token）
- 代码场景下中英混杂容易导致输出不稳定

需要中文交互时，控制用户侧语言即可，prompt 本身保持英文。

## 相对 s02 的变更

| 组件         | s02          | s03                          |
|-------------|-------------|------------------------------|
| System prompt | 单行字符串  | 分层模板 + 动态上下文注入      |
| Agent loop   | 不变        | 不变                          |

## 试一试

```bash
python agents/s03_system_prompt.py
```

推荐 prompt：

1. `Create a Python calculator module with add, subtract, multiply, divide`
2. `Look at all Python files here and tell me the coding style`
3. `Refactor hello.py: add type hints and a proper main guard`
