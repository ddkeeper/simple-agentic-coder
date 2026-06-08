"""Anthropic API client wrapper (synchronous + streaming)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Generator, Literal

import httpx
from anthropic import Anthropic

from utils.logger import Logger


@dataclass
class StreamEvent:
    """Normalized streaming event yielded by send_stream()."""
    type: Literal["stream_start", "text_delta", "tool_start", "tool_delta", "stream_end"]
    text: str = ""
    tool_name: str = ""
    tool_id: str = ""
    tool_input_json: str = ""


@dataclass
class StreamContext:
    """Accumulates state during streaming. Available after iteration."""
    text: str = ""
    content_blocks: list = field(default_factory=list)
    stop_reason: str = ""
    usage: dict = field(default_factory=dict)
    interrupted: bool = False
    current_block_type: str = ""


class AnthropicClient:
    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        logger: Logger | None = None,
        timeout: float = 60.0,
    ):
        self.model = model
        base_url = os.getenv("ANTHROPIC_BASE_URL")
        # Prevent proxy software (Clash/V2Ray) from injecting auth headers
        # via the ANTHROPIC_AUTH_TOKEN env var
        os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)
        client_kwargs: dict = {"timeout": timeout}
        if base_url:
            client_kwargs["base_url"] = base_url
        # Use direct connection (bypass system proxy) to avoid SSL issues
        transport = httpx.HTTPTransport(proxy=None, trust_env=False)
        client_kwargs["http_client"] = httpx.Client(
            transport=transport, proxy=None, trust_env=False
        )
        self.client = Anthropic(**client_kwargs)
        self.logger = logger or Logger()

    def send(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 8000,
    ):
        kwargs = dict(
            model=self.model,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
        )
        if tools:
            kwargs["tools"] = tools

        self.logger.log("request", {
            "model": self.model,
            "message_count": len(messages),
            "tool_count": len(tools) if tools else 0,
        })

        response = self.client.messages.create(**kwargs)

        self.logger.log("response", {
            "stop_reason": response.stop_reason,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            "content_blocks": len(response.content),
        })

        return response

    def send_stream(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 8000,
    ) -> Generator[tuple[StreamContext, StreamEvent], None, None]:
        """Streaming LLM call.

        Yields (ctx, event) tuples. First yield gives StreamContext
        (capture it, then pass remaining generator to stream_print).
        After iteration, ctx holds: text, content_blocks, stop_reason,
        usage, interrupted, current_block_type.
        """
        kwargs = dict(
            model=self.model,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
        )
        if tools:
            kwargs["tools"] = tools

        self.logger.log("request", {
            "model": self.model,
            "message_count": len(messages),
            "tool_count": len(tools) if tools else 0,
        })

        ctx = StreamContext()

        try:
            with self.client.messages.stream(**kwargs) as stream:
                yield ctx, StreamEvent(type="stream_start")

                for event in stream:
                    if event.type == "message_start":
                        ctx.usage["input_tokens"] = event.message.usage.input_tokens

                    elif event.type == "content_block_start":
                        block = event.content_block
                        if block.type == "text":
                            ctx.current_block_type = "text"
                        elif block.type == "tool_use":
                            ctx.current_block_type = "tool_use"
                            yield ctx, StreamEvent(
                                type="tool_start",
                                tool_name=block.name,
                                tool_id=block.id,
                            )

                    elif event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            ctx.text += event.delta.text
                            yield ctx, StreamEvent(type="text_delta", text=event.delta.text)
                        elif event.delta.type == "input_json_delta":
                            yield ctx, StreamEvent(
                                type="tool_delta",
                                tool_input_json=event.delta.partial_json,
                            )

                    elif event.type == "message_delta":
                        if hasattr(event.usage, "input_tokens") and event.usage.input_tokens:
                            ctx.usage["input_tokens"] = event.usage.input_tokens
                        if event.usage.output_tokens:
                            ctx.usage["output_tokens"] = event.usage.output_tokens
                        if event.delta.stop_reason:
                            ctx.stop_reason = event.delta.stop_reason

                # Get the final assembled message (includes complete content blocks)
                final_message = stream.get_final_message()
                ctx.content_blocks = final_message.content
                if final_message.stop_reason:
                    ctx.stop_reason = final_message.stop_reason

            self.logger.log("response", {
                "stop_reason": ctx.stop_reason,
                "usage": ctx.usage,
                "content_blocks": len(ctx.content_blocks),
            })

        except KeyboardInterrupt:
            ctx.interrupted = True
            if not ctx.stop_reason:
                ctx.stop_reason = "interrupted"
            self.logger.log("response_interrupted", {
                "current_block_type": ctx.current_block_type,
                "text_length": len(ctx.text),
                "usage": ctx.usage,
            })

        yield ctx, StreamEvent(type="stream_end")
