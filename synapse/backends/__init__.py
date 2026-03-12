"""
synapse/backends/__init__.py

Two backends. That's all.

  openai   → anything speaking the OpenAI chat format
             (OpenAI, Groq, Together, OpenRouter, Ollama, GLM, LM Studio, ...)

  anthropic → Anthropic Claude (genuinely different SDK)

The user configures which provider via model + api_key + base_url.
No new files needed when a new provider launches.
"""

from synapse.backends.openai_compatible import OpenAICompatibleBackend
from synapse.backends.anthropic import AnthropicBackend


def get_backend(name: str, **kwargs):
    name = name.lower().strip()

    if name in ("openai", "groq", "together", "openrouter", "ollama",
                "lmstudio", "mistral", "perplexity", "fireworks",
                "gemini", "google"):
        return OpenAICompatibleBackend(**kwargs)

    elif name == "anthropic":
        return AnthropicBackend(**kwargs)

    else:
        raise ValueError(
            f"Unknown backend: '{name}'\n"
            f"Use 'openai' for any OpenAI-compatible API, or 'anthropic' for Claude.\n\n"
            f"Examples:\n"
            f"  OpenAI:     backend='openai', model='gpt-4o'\n"
            f"  Gemini:     backend='openai', model='gemini-1.5-pro',\n"
            f"              base_url='https://generativelanguage.googleapis.com/v1beta/openai/'\n"
            f"  Groq:       backend='openai', model='llama3-8b-8192',\n"
            f"              base_url='https://api.groq.com/openai/v1'\n"
            f"  OpenRouter: backend='openai', model='mistralai/mixtral-8x7b',\n"
            f"              base_url='https://openrouter.ai/api/v1'\n"
            f"  Ollama:     backend='openai', model='llama3',\n"
            f"              base_url='http://localhost:11434/v1'\n"
            f"  GLM:        backend='openai', model='glm-4',\n"
            f"              base_url='https://open.bigmodel.cn/api/paas/v4'\n"
            f"  Anthropic:  backend='anthropic', model='claude-sonnet-4-6'"
        )


__all__ = ["get_backend", "OpenAICompatibleBackend", "AnthropicBackend"]
