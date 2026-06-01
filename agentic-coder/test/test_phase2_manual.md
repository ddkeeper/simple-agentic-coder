# Phase 2 人工对话测试指南

启动方式：
```bash
cd agentic-coder
python main.py
```

每项测试标注了预期行为，出现不符则视为失败。

---

## 1. prompt_toolkit 输入模块

测试目标：多行输入、粘贴、空输入、退出。

### 1.1 单行输入（基础）

```
>> What is Python?
```

预期：正常提交，模型开始流式输出。

### 1.2 多行粘贴

在 `>>` 提示符下，直接粘贴以下代码块（不手动换行）：

```
def hello():
    print("hello")
    return 42
```

预期：粘贴后内容完整显示，按 Enter 提交，模型能看到完整的三行代码。

### 1.3 Alt+Enter 多行输入

先输入第一行，然后按 Alt+Enter（不是 Enter），再输入第二行，最后按 Enter 提交：

```
>> List these two files:
.. main.py
.. requirements.txt
```

预期：第一行后提示符变为 `..`（续行），Alt+Enter 后光标到下一行，Enter 提交完整两行内容。

### 1.4 空输入不退出

直接按 Enter（不输入任何内容）。

预期：重新显示 `>>`，不退出程序，不发送 API 请求。

### 1.5 退出

输入 `q` 然后 Enter。再重新启动，输入 `exit` 然后 Enter。

预期：两次都正常退出，无报错。

---

## 2. 流式输出

测试目标：文字逐字出现、Markdown 渲染、tool_use 提示。

### 2.1 纯文本流式输出

```
>> Explain what a Python decorator is in 3 sentences.
```

预期：文字逐字（逐词）出现在屏幕上，不是一次性全部弹出。Markdown 格式（如有）正确渲染。

### 2.2 带代码块的流式输出

```
>> Write a Python function that checks if a number is prime. Include a docstring and type hints.
```

预期：代码块以 Markdown 格式渲染（有背景色或缩进），不是原始的三反引号文本。

### 2.3 tool_use 流式提示

```
>> List all Python files in the current directory.
```

预期：模型先输出一段文字说明，然后出现一行暗色 `calling glob_search...`，接着显示工具结果，最后模型给出总结。

---

## 3. Ctrl+C 中断

测试目标：中断后上下文保留，不报错，能继续对话。

### 3.1 纯文本生成时中断

```
>> Write a very long essay about the history of programming languages, at least 500 words.
```

在文字正在输出的过程中（还没结束时）按 Ctrl+C。

预期：
- 输出立即停止
- 显示 `[generation interrupted]`
- 回到 `>>` 输入提示符
- **不报错、不崩溃**

### 3.2 中断后继续对话

紧接着 3.1，输入：

```
>> What were you just talking about? Summarize in one sentence.
```

预期：模型能回忆出刚才写了一部分"编程语言历史"的内容（说明上下文被保留了）。如果模型说"你打断了我"之类的话，也视为正常。

### 3.3 工具调用期间中断（可选）

```
>> Read all Python files in the current directory and summarize each one.
```

在工具执行过程中（或模型正在输出长结果时）按 Ctrl+C。

预期：中断干净，回到 `>>`，不残留半截 JSON。

---

## 4. Token 消耗回显

测试目标：每轮结束后显示 token 用量。

### 4.1 单轮 token 显示

```
>> What is 1+1?
```

预期：回答结束后，在下方显示一行暗色文字，格式类似：
```
  input: 1,234 tokens | output: 12 tokens
```

### 4.2 工具调用轮 token 显示

```
>> Read main.py
```

预期：工具调用后继续回答，最终显示 token 用量。如果有两次 LLM 调用（一次触发工具，一次总结），应显示最终那次的 token。

### 4.3 多轮 token 累积观察

连续问 3 个问题：
```
>> What is 1+1?
>> What is 2+2?
>> What is 3+3?
```

预期：每次回答后都显示 token。注意 `input` token 应该逐轮递增（因为上下文在累积）。

---

## 5. glob_search 工具

测试目标：文件通配符搜索功能。

### 5.1 基础搜索

```
>> Use glob_search to find all Python files: pattern "**/*.py", path "."
```

预期：返回项目中所有 `.py` 文件的相对路径列表。

### 5.2 模型自主调用

不直接提工具名，让模型自己判断：

```
>> What Python files exist in the tools/ directory?
```

预期：模型自主选择调用 `glob_search` 或 `list_files`，返回 `tools/` 下的文件列表。

### 5.3 无匹配结果

```
>> Search for any .java files in this project.
```

预期：返回 `(no matches)`，模型据此回答"没有 Java 文件"。

---

## 6. grep_search 工具

测试目标：正则内容搜索、行截断。

### 6.1 基础搜索

```
>> Search for "def " in all Python files in this project.
```

预期：返回 `文件名:行号: 代码行` 格式的结果，包含项目中所有函数定义。

### 6.2 模型自主调用

```
>> Where is the `auto_compact` function defined? Show me the file and line number.
```

预期：模型调用 `grep_search`，找到 `core/context.py` 中的定义。

### 6.3 特定文件类型搜索

```
>> Search for "import" only in .py files under the tools/ directory.
```

预期：只返回 `tools/` 下 `.py` 文件的匹配行。

### 6.4 正则表达式搜索

```
>> Find all function definitions that start with "print" using grep_search with regex pattern "def print\\w+".
```

预期：返回 `print_user`、`print_assistant`、`print_tool` 等函数定义。

---

## 附加：综合场景

### A. 创建文件 + 流式输出 + 工具调用

```
>> Create a file called test_output.py with a function that calculates fibonacci numbers, then read it back to confirm.
```

预期：
1. 流式输出过程中出现 `calling write_file...`
2. 工具执行后继续输出
3. 再次出现 `calling read_file...`
4. 最终确认文件内容正确
5. 显示 token 用量

### B. 多轮编码任务

```
>> Create a file called hello.py that prints "Hello, World!"
```
等待完成后：
```
>> Now modify it to accept a name argument and print "Hello, {name}!"
```
等待完成后：
```
>> Run it with python hello.py and show me the output
```

预期：三轮对话中模型记得之前创建的文件路径和内容，每次修改都基于上一轮的结果。
