"""
synapse/core.py
The main Synapse class - the public API that everything flows through.
"""

from __future__ import annotations
import os
from typing import Optional, Union
from pathlib import Path


class Synapse:
    """
    The Synapse framework entry point.

    Example:
        from synapse import Synapse

        # With a cloud backend
        app = Synapse(backend="openai", api_key="sk-...")

        # With a local backend
        app = Synapse(backend="ollama", model="llama3")

        # Inject a payload into a LoRA
        app.inject("./knowledge.md", key="secret123", lora="./my.lora")

        # Serve the API + dashboard
        app.serve(port=8000)
    """

    def __init__(
        self,
        backend: str = "ollama",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        lora: Optional[str] = None,
    ):
        """
        Args:
            backend: One of "openai", "anthropic", "ollama", "groq", "together"
            model: Model name override. If None, uses sensible defaults per backend.
            api_key: API key for cloud backends. Can also be set via env vars.
            base_url: Custom base URL (useful for local OpenAI-compatible servers).
            lora: Path to a .lora/.pt/.bin file to load on startup.
        """
        self.backend_name = backend
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.lora_path = lora
        self._backend = None
        self._injector = None
        self._retrieval = None

        self._init_backend()

    def _init_backend(self):
        """Initialize the AI backend."""
        from synapse.backends import get_backend
        self._backend = get_backend(
            name=self.backend_name,
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
        )

    def configure(
        self,
        backend: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """Update backend settings at runtime."""
        if backend:
            self.backend_name = backend
        if model:
            self.model = model
        if api_key:
            self.api_key = api_key
        if base_url:
            self.base_url = base_url
        
        # Re-initialize backend with new settings
        self._init_backend()
        print(f"[synapse] Configuration updated: {self.backend_name} / {self.model}")

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(
        self,
        data_path: str,
        output_path: str,
        mode: str = "fast",
        reserve_bytes: int = 8192,
        **kwargs,
    ) -> str:
        """
        Train a LoRA on your documents via continued pre-training.
        The model genuinely learns the content — no retrieval needed
        for the parametric layer. Run inject() afterward to add the stego layer.

        Args:
            data_path:     File or directory (.txt, .md, .pdf, .docx, .html, .json)
            output_path:   Where to save the trained .lora
            mode:          "tiny" | "fast" (default) | "quality"
            reserve_bytes: Bytes to reserve for stego injection afterward
            **kwargs:      Forwarded to SynapseTrainer.train()

        Returns:
            output_path

        Example:
            app = Synapse(backend="ollama")
            app.train("./docs/", "./my.lora", mode="fast")
            app.inject("./secrets.md", key="mykey", lora="./my.lora")
            app.serve()
        """
        from synapse.train.trainer import SynapseTrainer

        trainer = SynapseTrainer(mode=mode)
        result = trainer.train(
            data_path=data_path,
            output_path=output_path,
            reserve_bytes=reserve_bytes,
            **kwargs,
        )
        # Auto-register so inject/serve don't need lora= repeated
        self.lora_path = result
        return result

    # ------------------------------------------------------------------
    # Payload operations
    # ------------------------------------------------------------------

    def inject(
        self,
        data: Union[str, Path],
        key: str,
        lora: Optional[str] = None,
        output: Optional[str] = None,
    ) -> str:
        """
        Hide data inside a LoRA file.

        Args:
            data: Path to a file OR a raw string to hide.
            key: The secret key used for PRNG mapping + encryption.
            lora: Path to the carrier LoRA file. Uses self.lora_path if not given.
            output: Where to save the modified LoRA. Defaults to overwriting input.

        Returns:
            Path to the output file.
        """
        from synapse.engine.injector import SynapseInjector

        lora_path = lora or self.lora_path
        if not lora_path:
            raise ValueError("No LoRA path specified. Pass lora= or set it on Synapse().")

        # Resolve payload bytes
        data_path = Path(data) if isinstance(data, str) else data
        if data_path.exists():
            payload = data_path.read_bytes()
        else:
            payload = str(data).encode("utf-8")

        injector = SynapseInjector(key)
        output_path = output or lora_path
        injector.inject_file(lora_path, payload, output_path)

        print(f"[synapse] ✓ Payload hidden in {output_path}")
        return output_path

    def extract(self, key: str, lora: Optional[str] = None) -> bytes:
        """
        Extract hidden payload from a LoRA file.

        Args:
            key: The secret key.
            lora: Path to the LoRA file.

        Returns:
            Raw bytes of the hidden payload.
        """
        from synapse.engine.injector import SynapseInjector

        lora_path = lora or self.lora_path
        if not lora_path:
            raise ValueError("No LoRA path specified.")

        injector = SynapseInjector(key)
        return injector.extract_file(lora_path)

    def unlock(self, key: str, lora: Optional[str] = None):
        """
        Unlock and load the hidden context into memory for RAG.
        After calling this, queries will use the hidden knowledge.

        Args:
            key: The secret key.
            lora: Path to the LoRA file.
        """
        from synapse.engine.retrieval import RetrievalStore

        payload = self.extract(key=key, lora=lora)
        text = payload.decode("utf-8", errors="ignore").strip("\x00")

        self._retrieval = RetrievalStore()
        self._retrieval.load(text)
        print(f"[synapse] ✓ Context unlocked. {len(text)} chars, {self._retrieval.chunk_count} chunks indexed.")

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(self, prompt: str, key: Optional[str] = None, lora: Optional[str] = None) -> dict:
        """
        Query the model. If a key is provided and context isn't already loaded,
        it will attempt to unlock the LoRA first.

        Args:
            prompt: The user's question.
            key: Optional key to unlock hidden context on-the-fly.
            lora: Optional LoRA path override.

        Returns:
            dict with "response", "context_used", and "unlocked" fields.
        """
        # Unlock on-the-fly if key provided and no context loaded
        if key and not self._retrieval:
            try:
                self.unlock(key=key, lora=lora)
            except Exception as e:
                print(f"[synapse] Could not unlock: {e}")

        context_chunks = []
        if self._retrieval:
            context_chunks = self._retrieval.retrieve(prompt, top_k=3)

        augmented_prompt = self._build_prompt(prompt, context_chunks)
        response = self._backend.complete(augmented_prompt)

        return {
            "response": response,
            "context_used": bool(context_chunks),
            "unlocked": self._retrieval is not None,
            "chunks": context_chunks,
        }

    def _build_prompt(self, prompt: str, chunks: list[str]) -> str:
        if not chunks:
            return prompt
        context = "\n\n".join(chunks)
        return (
            f"You have access to the following private knowledge:\n\n"
            f"{context}\n\n"
            f"---\n"
            f"Using the above context where relevant, answer:\n{prompt}"
        )

    # ------------------------------------------------------------------
    # Server
    # ------------------------------------------------------------------

    def serve(self, host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
        """
        Start the Synapse API server + dashboard.

        Dashboard: http://localhost:{port}
        API docs:  http://localhost:{port}/docs
        """
        import uvicorn
        from synapse.server.app import create_app

        app = create_app(synapse=self)
        print(f"\n[synapse] 🚀 Server starting")
        print(f"[synapse]    Dashboard → http://localhost:{port}")
        print(f"[synapse]    API docs  → http://localhost:{port}/docs")
        print(f"[synapse]    Backend   → {self.backend_name}\n")
        uvicorn.run(app, host=host, port=port, reload=reload)

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(
        self,
        data,
        output: str,
        mode: str = "fast",
        reserve_bytes: int = 8192,
        **kwargs,
    ):
        """
        Train a LoRA on your documents via continued pre-training.
        
        Args:
            data: Path to file or directory of .txt/.md documents
            output: Where to save the trained .lora file  
            mode: "fast" (1B model ~2min CPU) or "quality" (7B ~20min CPU)
            reserve_bytes: Bytes to reserve for stego injection afterward
        """
        from synapse.train.trainer import SynapseTrainer
        trainer = SynapseTrainer(mode=mode)
        trainer.train(data_path=str(data), output_path=output, reserve_bytes=reserve_bytes, **kwargs)
        return output

    # ------------------------------------------------------------------
    # Bridge — LLM-to-LLM
    # ------------------------------------------------------------------

    def pack_bridge(self, key: str, output: str = "handoff.bridge") -> str:
        """Pack current context into a bridge file for another LLM instance."""
        from synapse.transfer.bridge import SynapseBridge
        return SynapseBridge().pack_from_synapse(self, key=key, output=output)

    def unpack_bridge(self, bridge_file: str, key: str):
        """Load context from a bridge file. After this, queries use the transferred context."""
        from synapse.transfer.bridge import SynapseBridge
        SynapseBridge().unpack_to_synapse(bridge_file, key=key, synapse_instance=self)

    # ------------------------------------------------------------------
    # Memory
    # ------------------------------------------------------------------

    @property
    def memory(self):
        """Access the persistent memory manager."""
        if not hasattr(self, '_memory_instance'):
            from synapse.memory.manager import MemoryManager
            self._memory_instance = MemoryManager()
        return self._memory_instance
