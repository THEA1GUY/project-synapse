"""
synapse/backends/openai_compatible.py

Handles any API that speaks the OpenAI chat format.
This covers: OpenAI, Groq, Together, OpenRouter, GLM, Ollama,
LM Studio, Mistral, Perplexity, Fireworks, and anything else
that follows the same spec.

The user just points it at the right URL.
"""

from __future__ import annotations
import os
from typing import Optional
from openai import OpenAI


class OpenAICompatibleBackend:

    name = "openai"

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        if not model:
            raise ValueError(
                "model is required.\n"
                "Example: Synapse(backend='openai', model='gpt-4o', api_key='sk-...')\n"
                "For other providers pass base_url too:\n"
                "  Groq:       base_url='https://api.groq.com/openai/v1'\n"
                "  OpenRouter: base_url='https://openrouter.ai/api/v1'\n"
                "  Ollama:     base_url='http://localhost:11434/v1'\n"
                "  GLM:        base_url='https://open.bigmodel.cn/api/paas/v4'"
            )

        self.model    = model
        self.api_key  = api_key or os.environ.get("OPENAI_API_KEY") or "no-key"
        self.base_url = base_url  # None = default OpenAI endpoint

        # OpenRouter-specific optimizations
        self.headers = {
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "Synapse RAG"
        }

        if self.base_url and "openrouter.ai" in self.base_url and "/" not in self.model:
            # Auto-prefix common models for OpenRouter
            if self.model.startswith("gpt"): self.model = "openai/" + self.model
            elif self.model.startswith("claude"): self.model = "anthropic/" + self.model
            elif self.model.startswith("llama"): self.model = "meta-llama/" + self.model
            elif self.model.startswith("gemini"): self.model = "google/" + self.model
            print(f"[synapse] OpenRouter auto-prefix applied: {self.model}")

    def complete(self, prompt: str, system: Optional[str] = None) -> str:
        # If model is "mock" return a fake response without calling any API
        """Get a full completion from the model."""
        # Mock model handling
        if self.model == "mock":
            return f"[MOCK RESPONSE] Using backend '{self.name}'. Prompt: {prompt[:50]}..."

        client = OpenAI(api_key=self.api_key, base_url=self.base_url, default_headers=self.headers)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            return f"Error from {self.name}: {str(e)}"

    def stream(self, prompt: str, system: Optional[str] = None):
        """Generator that yields text chunks as they arrive."""
        if self.model == "mock":
            words = f"[MOCK STREAM] Using backend '{self.name}'. Prompt: {prompt[:50]}...".split()
            for word in words:
                yield word + " "
            return

        client = OpenAI(api_key=self.api_key, base_url=self.base_url, default_headers=self.headers)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            stream = client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True
            )
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as e:
            yield f"\n[STREAM ERROR] {str(e)}"

    def health_check(self) -> dict:
        try:
            result = self.complete("Reply with just the word OK.")
            return {"ok": True, "detail": result.strip()}
        except Exception as e:
            return {"ok": False, "detail": str(e)}

    def __repr__(self):
        url = self.base_url or "api.openai.com"
        return f"OpenAICompatibleBackend(model={self.model!r}, url={url!r})"
