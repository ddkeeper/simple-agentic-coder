"""Anthropic API client wrapper (synchronous, non-streaming)."""

from __future__ import annotations

import os

import httpx
from anthropic import Anthropic

from utils.logger import Logger


class AnthropicClient:
    def __init__(self, model: str = "claude-sonnet-4-20250514", logger: Logger | None = None):
        self.model = model
        base_url = os.getenv("ANTHROPIC_BASE_URL")
        # Prevent proxy software (Clash/V2Ray) from injecting auth headers
        # via the ANTHROPIC_AUTH_TOKEN env var
        os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)
        client_kwargs: dict = {}
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
