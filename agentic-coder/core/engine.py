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
        from ui.console import print_info, print_tool

        self.messages.append({"role": "user", "content": user_input})
        tools = get_anthropic_tools()

        while True:
            # Context compression before each LLM call
            tokens = estimate_tokens(self.messages)
            print_info(f"  context: ~{tokens} tokens, {len(self.messages)} messages")
            microcompact(self.messages)
            auto_compact(self.messages, self.llm)

            response = self.llm.send(
                system=self.system_prompt,
                messages=self.messages,
                tools=tools,
            )

            # Append full assistant response
            self.messages.append({"role": "assistant", "content": response.content})

            # Extract text for display
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text

            # If no tool calls, we're done
            if response.stop_reason != "tool_use":
                return final_text

            # Execute each tool call
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    output = self._dispatch_tool(block.name, block.input)

                    # Git auto-commit after successful file writes
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
                        "_tool_name": block.name,  # for microcompact preservation
                    })

            # Append tool results as a user message
            if tool_results:
                self.messages.append({"role": "user", "content": tool_results})

    def _dispatch_tool(self, name: str, tool_input: dict) -> str:
        """Dispatch a tool call with HITL approval for dangerous tools."""
        from ui.hitl import check_approval

        if not self.auto_approve and not check_approval(name, tool_input):
            return "Error: User denied permission"

        return execute_tool(name, tool_input)
