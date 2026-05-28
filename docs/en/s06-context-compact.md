# s06: Context Compact

> **Key insight**: Context window is a finite resource — the biggest engineering problem in agents isn't capability, it's memory management.

## The Problem

After 20 rounds of work, messages may contain 50,000+ tokens. Much is intermediate tool output — already used, never needed again, but still taking up space. Either context explodes, or the LLM starts "forgetting" system prompt rules due to token overload.

## The Solution

When messages exceed a threshold, use the LLM itself to compress old messages into a summary, replacing the original content.

```
Before compact:
  [sys] [user_1] [asst_1] [user_2] [asst_2] ... [user_20] [asst_20]
  |<--- these are old, compressible --->|

After compact:
  [sys] [summary_of_rounds_1_to_15] [user_16] ... [user_20] [asst_20]
        |<--- one LLM call produces this summary --->|
```

## How It Works

1. Check token count in the agent loop.

```python
def estimate_tokens(messages):
    text = json.dumps(messages)
    return len(text) // 4  # rough estimate
```

2. When threshold exceeded, extract old messages and call LLM for summary.

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

3. System prompt is never compressed — always preserved in full.

## Compression Strategy Comparison

| Strategy     | Pros                 | Cons                              |
|-------------|----------------------|-----------------------------------|
| Sliding window | Simple, deterministic | Loses early information           |
| LLM summary  | Preserves semantics  | Extra API call, may miss details  |
| Hybrid       | Best of both         | Slightly more complex             |

This implementation uses LLM summary because it's Claude Code's actual strategy and the most instructive to understand.

## What Changed from s05

| Component    | s05           | s06                              |
|-------------|---------------|----------------------------------|
| Message mgmt | Unbounded growth | Auto-compact when threshold hit |
| Agent loop  | Unchanged     | + compact check logic            |
| New function | None          | `compact_messages()`             |

## Try It

```bash
python agents/s06_context_compact.py
```

Recommended prompts (multi-round, trigger compaction):

1. `Create a file called data.txt with 100 lines of random text`
2. `Read the file and tell me what's on line 50`
3. `Edit line 50 to say "modified by agent"`
4. `Now create 5 more files with different content`
5. `Read all 6 files and give me a summary of each` — should trigger compact
