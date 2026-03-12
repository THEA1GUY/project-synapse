"""
synapse/backends/anthropic.py

Anthropic Claude — the only provider that uses a genuinely different SDK
and API format, so it gets its own file.
"""

from __future__ import annotations
import os
from typing import Optional


class AnthropicBackend:

    name = "anthropic"

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        if not model:
            raise ValueError(
                "model is required.\n"
                "Example: Synapse(backend='anthropic', model='claude-sonnet-4-6', "
                "api_key='sk-ant-...')"
            )

        self.model    = model
        self.api_key  = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.base_url = base_url

        if not self.api_key:
            raise ValueError(
                "Anthropic requires an API key.\n"
                "Pass api_key= or set the ANTHROPIC_API_KEY environment variable."
            )

    def complete(self, prompt: str, system: Optional[str] = None) -> str:
        try:
            import anthropic
        except ImportError:
            raise ImportError("Run: pip install anthropic")

        client = anthropic.Anthropic(api_key=self.api_key)
        kwargs = dict(
            model=self.model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        if system:
            kwargs["system"] = system

        resp = client.messages.create(**kwargs)
        return resp.content[0].text

    def health_check(self) -> dict:
        try:
            result = self.complete("Reply with just the word OK.")
            return {"ok": True, "detail": result.strip()}
        except Exception as e:
            return {"ok": False, "detail": str(e)}

    def __repr__(self):
        return f"AnthropicBackend(model={self.model!r})"
