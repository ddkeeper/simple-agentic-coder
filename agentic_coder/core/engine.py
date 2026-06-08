"""Core ReAct agent loop.

The loop is invariant: LLM call -> check stop -> dispatch tools -> repeat.
All features (context compression, git auto-commit, HITL) plug into this loop.
"""

from __future__ import annotations

from pathlib import Path

from core.context import auto_compact, estimate_tokens, microcompact
from core.llm import AnthropicClient
from tools.git import git_auto_commit
from tools.registry import execute_tool, get_anthropic_tools


class Engine:
    def __init__(self, llm_client: AnthropicClient, system_prompt: str, auto_approve: bool = False):
        self.llm = llm_client
        self.system_prompt = system_prompt
        self.auto_approve = auto_approve
        self.messages: list[dict] = []

    def run(self, user_input: str) -> str:
        """Process one user turn. Returns the final assistant text."""
        from ui.console import print_info, print_tool, print_token_usage, stream_print

        self.messages.append({"role": "user", "content": user_input})
        tools = get_anthropic_tools()

        # Show context state once per user turn
        tokens = estimate_tokens(self.messages)
        print_info(f"  context: ~{tokens} tokens, {len(self.messages)} messages")

        # Accumulate token usage across all LLM calls in this turn
        turn_usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}

        while True:
            # Context compression before each LLM call
            microcompact(self.messages)
            auto_compact(self.messages, self.llm)

            # --- Streaming LLM call ---
            gen = self.llm.send_stream(
                system=self.system_prompt,
                messages=self.messages,
                tools=tools,
            )

            try:
                ctx, _first_event = next(gen)
            except StopIteration:
                return ""

            try:
                stream_print(gen)
            except KeyboardInterrupt:
                ctx.interrupted = True

            # Accumulate token usage
            turn_usage["input_tokens"] += ctx.usage.get("input_tokens", 0)
            turn_usage["output_tokens"] += ctx.usage.get("output_tokens", 0)

            # --- API error handling ---
            if ctx.api_error:
                from ui.console import print_error
                print_error(f"API error: {ctx.api_error}")
                return ""

            # --- Interrupt handling ---
            if ctx.interrupted:
                safe_content = []
                for block in ctx.content_blocks:
                    if getattr(block, "type", None) == "text":
                        safe_content.append({"type": "text", "text": block.text})
                if not safe_content and ctx.text:
                    safe_content.append({"type": "text", "text": ctx.text})
                safe_content.append({
                    "type": "text",
                    "text": "\n[User interrupted the generation]",
                })
                self.messages.append({"role": "assistant", "content": safe_content})
                print_info("\ngeneration interrupted")
                print_token_usage(turn_usage)
                return ""

            # --- Normal path ---
            self.messages.append({"role": "assistant", "content": ctx.content_blocks})

            if ctx.stop_reason != "tool_use":
                print_token_usage(turn_usage)
                return ctx.text

            # Execute each tool call
            tool_results = []
            for block in ctx.content_blocks:
                if hasattr(block, "type") and block.type == "tool_use":
                    output = self._dispatch_tool(block.name, block.input)

                    if block.name in ("write_file", "edit_file") and not output.startswith("Error"):
                        path = block.input.get("path", "")
                        abs_path = str(Path(path).expanduser().resolve())
                        commit_hash = git_auto_commit(abs_path, f"{block.name}: {path}")
                        if commit_hash:
                            output += f"\n[committed as {commit_hash}]"

                    print_tool(block.name, output)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": output,
                        "_tool_name": block.name,
                    })

            if tool_results:
                self.messages.append({"role": "user", "content": tool_results})

    def _dispatch_tool(self, name: str, tool_input: dict) -> str:
        """Dispatch a tool call with HITL approval for dangerous tools."""
        from ui.hitl import check_approval

        if not self.auto_approve and not check_approval(name, tool_input):
            return "Error: User denied permission"

        return execute_tool(name, tool_input)
