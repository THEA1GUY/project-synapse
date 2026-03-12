"""
synapse/train/trainer.py

Continued pre-training on raw documents.
No synthetic pairs. No labels. The document IS the training signal.

The model reads your text and the knowledge gets baked into the LoRA weights.
At inference time it just knows it — no retrieval needed for parametric knowledge.
The stego layer sits on top for dynamic/sensitive content.

Architecture:
  - Continued causal language modeling on raw text (next-token prediction)
  - Only LoRA matrices trained — base model frozen
  - Three-tier backend fallback: Unsloth → PEFT+BnB → PEFT+float32
  - Gradient checkpointing always on for CPU memory efficiency
  - Overlap-aware chunking to preserve knowledge at boundaries
  - RAM estimation before training starts
  - Cosine LR schedule with warmup
  - Packing (multiple docs per sequence) for faster throughput

Performance targets on CPU:
  Mode     Model           RAM      Time
  ------   -----------     ------   ----------
  tiny     TinyLlama-1.1B  2-3GB    <1 min
  fast     Phi-3-mini      4-6GB    2-5 min
  quality  Llama-3-8B      8-12GB   15-30 min
"""

from __future__ import annotations

import gc
import os
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional


# ---------------------------------------------------------------------------
# Model presets
# ---------------------------------------------------------------------------

@dataclass
class ModelPreset:
    hf_id: str
    fallback_id: str
    rank: int
    lora_alpha_multiplier: int
    target_modules: list
    description: str
    ram_gb_estimate: float


PRESETS: dict[str, ModelPreset] = {
    "tiny": ModelPreset(
        hf_id="unsloth/tinyllama-bnb-4bit",
        fallback_id="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        rank=4,
        lora_alpha_multiplier=2,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        description="TinyLlama ~1.1B — trains in <1min on CPU",
        ram_gb_estimate=2.5,
    ),
    "fast": ModelPreset(
        hf_id="unsloth/Phi-3-mini-4k-instruct-bnb-4bit",
        fallback_id="microsoft/phi-2",
        rank=8,
        lora_alpha_multiplier=2,
        target_modules=["q_proj", "k_proj", "v_proj", "dense"],
        description="Phi-3-mini ~3.8B — trains in 2-5min on CPU",
        ram_gb_estimate=4.5,
    ),
    "quality": ModelPreset(
        hf_id="unsloth/llama-3-8b-bnb-4bit",
        fallback_id="meta-llama/Meta-Llama-3-8B",
        rank=16,
        lora_alpha_multiplier=2,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        description="Llama-3-8B ~8B — trains in 15-30min on CPU",
        ram_gb_estimate=10.0,
    ),
}


# ---------------------------------------------------------------------------
# Document loader
# ---------------------------------------------------------------------------

class DocumentLoader:
    """
    Load text from files or directories.
    Supported natively:  .txt .md .rst .html .json .csv
    Supported optionally: .pdf (pip install pypdf)
                          .docx (pip install python-docx)
    """

    NATIVE   = {".txt", ".md", ".rst", ".markdown", ".html", ".htm",
                ".json", ".csv"}
    OPTIONAL = {".pdf", ".docx"}

    def load(self, path: str) -> list[str]:
        """Return a list of raw text strings, one per file."""
        p = Path(path)
        if p.is_file():
            return [self._read(p)]
        elif p.is_dir():
            return self._read_dir(p)
        raise FileNotFoundError(f"Not found: {path}")

    def _read_dir(self, p: Path) -> list[str]:
        texts = []
        for ext in sorted(self.NATIVE | self.OPTIONAL):
            for f in sorted(p.rglob(f"*{ext}")):
                try:
                    t = self._read(f)
                    if t.strip():
                        texts.append(t)
                except Exception as e:
                    print(f"      [!] Skipping {f.name}: {e}")
        if not texts:
            raise ValueError(
                f"No readable text files in {p}. "
                f"Supported: {', '.join(sorted(self.NATIVE | self.OPTIONAL))}"
            )
        return texts

    def _read(self, p: Path) -> str:
        ext = p.suffix.lower()

        if ext in (".txt", ".md", ".rst", ".markdown"):
            return p.read_text(encoding="utf-8", errors="ignore")

        elif ext in (".html", ".htm"):
            raw = p.read_text(encoding="utf-8", errors="ignore")
            return self._strip_html(raw)

        elif ext == ".json":
            import json
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, list):
                parts = []
                for item in data:
                    if isinstance(item, dict):
                        parts.append(
                            item.get("text") or item.get("content") or
                            item.get("body") or str(item)
                        )
                    else:
                        parts.append(str(item))
                return "\n".join(str(p) for p in parts)
            return json.dumps(data, indent=2)

        elif ext == ".csv":
            return p.read_text(encoding="utf-8", errors="ignore")

        elif ext == ".pdf":
            try:
                import pypdf
                reader = pypdf.PdfReader(str(p))
                return "\n".join(pg.extract_text() or "" for pg in reader.pages)
            except ImportError:
                raise ImportError("pip install pypdf")

        elif ext == ".docx":
            try:
                import docx
                doc = docx.Document(str(p))
                return "\n".join(para.text for para in doc.paragraphs)
            except ImportError:
                raise ImportError("pip install python-docx")

        # Fallback — try as text
        return p.read_text(encoding="utf-8", errors="ignore")

    @staticmethod
    def _strip_html(raw: str) -> str:
        from html.parser import HTMLParser

        class _S(HTMLParser):
            def __init__(self):
                super().__init__()
                self.parts = []
            def handle_data(self, d):
                self.parts.append(d)

        s = _S()
        s.feed(raw)
        return " ".join(s.parts)


# ---------------------------------------------------------------------------
# Chunker
# ---------------------------------------------------------------------------

class DocumentChunker:
    """
    Split documents into overlapping training chunks.

    Why overlap matters: without it, the model never learns the information
    at the seam between two chunks. Overlap ensures every sentence appears
    in at least two training examples with different context around it.
    """

    def __init__(self, max_tokens: int = 512, overlap_ratio: float = 0.125):
        self.max_tokens = max_tokens
        self.overlap_tokens = max(32, int(max_tokens * overlap_ratio))

    def chunk(self, texts: list[str], tokenizer=None) -> list[str]:
        chunks = []
        for text in texts:
            chunks.extend(self._chunk_one(text.strip(), tokenizer))
        # Remove very short fragments (likely header/footer noise)
        return [c for c in chunks if len(c.split()) >= 8]

    def _chunk_one(self, text: str, tokenizer=None) -> list[str]:
        if not text:
            return []
        # Split on paragraph breaks first for semantic coherence
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if tokenizer:
            return self._chunk_by_tokens(paragraphs, tokenizer)
        return self._chunk_by_words(paragraphs)

    def _chunk_by_tokens(self, paragraphs: list[str], tokenizer) -> list[str]:
        chunks = []
        current_ids = []
        current_parts = []

        for para in paragraphs:
            ids = tokenizer.encode(para, add_special_tokens=False)
            if len(current_ids) + len(ids) > self.max_tokens and current_parts:
                chunks.append("\n\n".join(current_parts))
                # Overlap: keep the last overlap_tokens of context
                keep_ids = current_ids[-self.overlap_tokens:]
                overlap_text = tokenizer.decode(keep_ids, skip_special_tokens=True)
                current_ids = keep_ids
                current_parts = [overlap_text]
            current_ids.extend(ids)
            current_parts.append(para)

        if current_parts:
            chunks.append("\n\n".join(current_parts))
        return chunks

    def _chunk_by_words(self, paragraphs: list[str]) -> list[str]:
        # 1 token ≈ 0.75 words
        max_words = int(self.max_tokens * 0.75)
        overlap_words = int(self.overlap_tokens * 0.75)
        chunks = []
        current = []

        for para in paragraphs:
            words = para.split()
            if len(current) + len(words) > max_words and current:
                chunks.append(" ".join(current))
                current = current[-overlap_words:]
            current.extend(words)

        if current:
            chunks.append(" ".join(current))
        return chunks


# ---------------------------------------------------------------------------
# Progress display
# ---------------------------------------------------------------------------

class Progress:
    """Degrades gracefully: tqdm if installed, else plain print."""

    def __init__(self, total: int, desc: str = ""):
        self.total = total
        self.current = 0
        self.start = time.time()
        self._bar = None
        try:
            from tqdm import tqdm
            self._bar = tqdm(total=total, desc=f"      {desc}", unit="step",
                             dynamic_ncols=True)
        except ImportError:
            print(f"      (install tqdm for a progress bar)")

    def update(self, n: int = 1, loss: float = None):
        self.current += n
        if self._bar:
            post = {"loss": f"{loss:.4f}"} if loss else {}
            self._bar.set_postfix(post)
            self._bar.update(n)
        else:
            interval = max(1, self.total // 20)
            if self.current % interval == 0 or self.current == self.total:
                elapsed = time.time() - self.start
                eta = (elapsed / max(self.current, 1)) * (self.total - self.current)
                pct = (self.current / max(self.total, 1)) * 100
                loss_str = f"  loss={loss:.4f}" if loss else ""
                print(f"      [{pct:5.1f}%] {self.current}/{self.total}{loss_str}"
                      f"  ETA {eta:.0f}s")

    def close(self):
        if self._bar:
            self._bar.close()


# ---------------------------------------------------------------------------
# RAM check
# ---------------------------------------------------------------------------

def _available_ram_gb() -> float:
    try:
        import psutil
        return psutil.virtual_memory().available / (1024 ** 3)
    except ImportError:
        return -1.0


# ---------------------------------------------------------------------------
# Main trainer
# ---------------------------------------------------------------------------

class SynapseTrainer:
    """
    Train a LoRA via continued pre-training on raw documents.

    Usage:
        trainer = SynapseTrainer(mode="fast")
        trainer.train("./my_docs/", "./output.lora")

    Or via the module-level shortcut:
        from synapse.train import train
        train("./my_docs/", "./output.lora", mode="fast")
    """

    def __init__(
        self,
        mode: Literal["tiny", "fast", "quality"] = "fast",
        base_model: Optional[str] = None,
        rank: Optional[int] = None,
        max_seq_length: int = 512,
    ):
        if mode not in PRESETS:
            raise ValueError(f"mode must be one of {list(PRESETS)}, got {mode!r}")

        self.mode = mode
        self.preset = PRESETS[mode]
        self.model_id = base_model or self.preset.hf_id
        self.rank = rank or self.preset.rank
        self.max_seq_length = max_seq_length
        self._model = None
        self._tokenizer = None
        self._backend: Optional[str] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def train(
        self,
        data_path: str,
        output_path: str,
        reserve_bytes: int = 8192,
        epochs: int = 1,
        batch_size: int = 1,
        grad_accum: int = 16,
        learning_rate: float = 2e-4,
        weight_decay: float = 0.01,
        warmup_ratio: float = 0.05,
        checkpoint_every: int = 0,
        resume_from: Optional[str] = None,
        seed: int = 42,
    ) -> str:
        """
        Run continued pre-training.

        Args:
            data_path:        File or directory of documents
            output_path:      Where to save the .lora file
            reserve_bytes:    Bytes to reserve in weight space for stego injection
            epochs:           Training epochs (1 is usually enough)
            batch_size:       Keep at 1 for CPU to avoid OOM
            grad_accum:       Effective batch = batch_size × grad_accum
            learning_rate:    Peak LR (cosine schedule)
            weight_decay:     AdamW weight decay
            warmup_ratio:     Fraction of steps for linear LR warmup
            checkpoint_every: Save every N steps (0 = disabled)
            resume_from:      Resume from a checkpoint directory
            seed:             Random seed

        Returns:
            output_path
        """
        random.seed(seed)
        t0 = time.time()

        # ── Header ──────────────────────────────────────────────────────
        print(f"\n{'─'*52}")
        print(f"  SYNAPSE TRAINER")
        print(f"{'─'*52}")
        print(f"  Mode:     {self.mode}  ({self.preset.description})")
        print(f"  Model:    {self.model_id}")
        print(f"  Data:     {data_path}")
        print(f"  Output:   {output_path}")
        print(f"  Rank:     {self.rank}   Seq len: {self.max_seq_length}")
        print(f"  Stego:    {reserve_bytes:,} bytes reserved")
        print(f"{'─'*52}")

        # ── RAM check ───────────────────────────────────────────────────
        avail = _available_ram_gb()
        needed = self.preset.ram_gb_estimate
        if avail > 0:
            ok = avail >= needed
            icon = "✓" if ok else "⚠"
            warn = "" if ok else f"  — need ~{needed}GB. May OOM. Try mode='tiny'"
            print(f"\n  {icon} RAM: {avail:.1f}GB available{warn}")

        # ── Step 1: Load documents ───────────────────────────────────────
        print(f"\n[1/5] Loading documents from {data_path}...")
        loader = DocumentLoader()
        texts = loader.load(data_path)
        total_chars = sum(len(t) for t in texts)
        print(f"      {len(texts)} file(s) — {total_chars:,} characters")

        # ── Step 2: Load model ───────────────────────────────────────────
        print(f"\n[2/5] Loading base model...")
        print(f"      First run downloads the model (~few GB).")
        self._load_model()
        print(f"      Backend: {self._backend}")
        trainable = sum(p.numel() for p in self._model.parameters()
                        if p.requires_grad)
        total_p  = sum(p.numel() for p in self._model.parameters())
        print(f"      Trainable params: {trainable:,} / {total_p:,} "
              f"({trainable/total_p*100:.2f}%)")

        # ── Step 3: Chunk ────────────────────────────────────────────────
        print(f"\n[3/5] Chunking documents...")
        chunker = DocumentChunker(
            max_tokens=self.max_seq_length,
            overlap_ratio=0.125,
        )
        chunks = chunker.chunk(texts, tokenizer=self._tokenizer)
        random.shuffle(chunks)
        est_tokens = int(sum(len(c) for c in chunks) / 4)
        print(f"      {len(chunks)} chunks — ~{est_tokens:,} tokens")
        print(f"      Effective batch: {batch_size} × {grad_accum} = "
              f"{batch_size * grad_accum}")
        total_steps = max(1, (len(chunks) // max(batch_size, 1)) * epochs)
        print(f"      Steps: {total_steps} ({epochs} epoch"
              f"{'s' if epochs > 1 else ''})")

        if len(chunks) < 4:
            print(f"\n  ⚠  Only {len(chunks)} chunks. "
                  f"Model will memorize but may overfit. Add more data for generalisation.")

        # ── Step 4: Train ────────────────────────────────────────────────
        print(f"\n[4/5] Training...")
        self._run_training(
            chunks=chunks,
            epochs=epochs,
            batch_size=batch_size,
            grad_accum=grad_accum,
            learning_rate=learning_rate,
            weight_decay=weight_decay,
            warmup_ratio=warmup_ratio,
            checkpoint_every=checkpoint_every,
            resume_from=resume_from,
            total_steps=total_steps,
            seed=seed,
        )

        # ── Step 5: Save ─────────────────────────────────────────────────
        print(f"\n[5/5] Saving LoRA...")
        self._save(output_path, reserve_bytes)

        elapsed = time.time() - t0
        m, s = divmod(int(elapsed), 60)
        print(f"\n{'─'*52}")
        print(f"  ✓ Done in {m}m {s}s")
        print(f"  ✓ Saved to: {output_path}")
        print(f"\n  Ready for:")
        print(f"    synapse inject --lora {output_path} \\")
        print(f"                   --data secrets.md --key mykey")
        print(f"{'─'*52}\n")
        return output_path

    # ------------------------------------------------------------------
    # Model loading — three-tier fallback
    # ------------------------------------------------------------------

    def _load_model(self):
        """
        Try loading backends in order of performance:
          1. Unsloth  — fastest, 4-bit, patched kernels (2-5x speedup)
          2. PEFT+BnB — 4-bit quantized via bitsandbytes
          3. PEFT+fp32 — no extra deps, slowest but always works
        """
        tiers = [
            (self._load_unsloth,   "unsloth"),
            (self._load_peft_bnb,  "peft+bitsandbytes"),
            (self._load_peft_fp32, "peft+float32"),
        ]
        for loader, name in tiers:
            try:
                loader()
                self._backend = name
                return
            except ImportError as e:
                msg = str(e).split("\n")[0]
                if name == "peft+float32":
                    raise RuntimeError(
                        f"Training failed — could not load any backend.\n"
                        f"Install at minimum: pip install transformers peft torch\n"
                        f"For best performance: pip install unsloth\n"
                        f"Error: {msg}"
                    ) from e
                print(f"      ({name} not available — {msg})")

    def _load_unsloth(self):
        from unsloth import FastLanguageModel

        model, tok = FastLanguageModel.from_pretrained(
            model_name=self.model_id,
            max_seq_length=self.max_seq_length,
            dtype=None,
            load_in_4bit=True,
        )
        model = FastLanguageModel.get_peft_model(
            model,
            r=self.rank,
            target_modules=self.preset.target_modules,
            lora_alpha=self.rank * self.preset.lora_alpha_multiplier,
            lora_dropout=0.0,
            bias="none",
            use_gradient_checkpointing="unsloth",
        )
        if tok.pad_token is None:
            tok.pad_token = tok.eos_token
        self._model, self._tokenizer = model, tok

    def _load_peft_bnb(self):
        from transformers import (AutoModelForCausalLM, AutoTokenizer,
                                   BitsAndBytesConfig)
        from peft import LoraConfig, get_peft_model, TaskType
        import bitsandbytes   # ImportError if not installed
        import torch

        bnb = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float32,
        )
        tok = AutoTokenizer.from_pretrained(self.model_id, use_fast=True)
        if tok.pad_token is None:
            tok.pad_token = tok.eos_token
        tok.padding_side = "right"

        model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            quantization_config=bnb,
            device_map="cpu",
            torch_dtype=torch.float32,
        )
        cfg = LoraConfig(
            r=self.rank,
            lora_alpha=self.rank * self.preset.lora_alpha_multiplier,
            target_modules=self.preset.target_modules,
            lora_dropout=0.05,
            bias="none",
            task_type=TaskType.CAUSAL_LM,
        )
        model = get_peft_model(model, cfg)
        model.enable_input_require_grads()
        model.gradient_checkpointing_enable()
        self._model, self._tokenizer = model, tok

    def _load_peft_fp32(self):
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import LoraConfig, get_peft_model, TaskType
        import torch

        # Use the smaller fallback model for float32 — the main model may be too large
        model_id = self.preset.fallback_id
        print(f"      Loading fallback: {model_id} (float32, no quantization)")
        print(f"      Tip: pip install unsloth  for much faster training")

        tok = AutoTokenizer.from_pretrained(model_id, use_fast=True)
        if tok.pad_token is None:
            tok.pad_token = tok.eos_token

        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            device_map="cpu",
            torch_dtype=torch.float32,
            low_cpu_mem_usage=True,
        )
        # Use minimal target modules for float32 to reduce memory
        cfg = LoraConfig(
            r=self.rank,
            lora_alpha=self.rank * self.preset.lora_alpha_multiplier,
            target_modules=["q_proj", "v_proj"],
            lora_dropout=0.05,
            bias="none",
            task_type=TaskType.CAUSAL_LM,
        )
        model = get_peft_model(model, cfg)
        model.enable_input_require_grads()
        model.gradient_checkpointing_enable()
        self._model, self._tokenizer = model, tok

    # ------------------------------------------------------------------
    # Training — TRL SFTTrainer if available, manual PyTorch loop fallback
    # ------------------------------------------------------------------

    def _run_training(
        self, chunks, epochs, batch_size, grad_accum,
        learning_rate, weight_decay, warmup_ratio,
        checkpoint_every, resume_from, total_steps, seed,
    ):
        try:
            from trl import SFTTrainer
            from datasets import Dataset
            self._train_trl(
                chunks, epochs, batch_size, grad_accum,
                learning_rate, weight_decay, warmup_ratio,
                checkpoint_every, resume_from, seed,
            )
        except ImportError:
            print("      (trl/datasets not installed — using manual loop)")
            print("      For faster training: pip install trl datasets")
            self._train_manual(
                chunks, epochs, batch_size, grad_accum,
                learning_rate, weight_decay, warmup_ratio, total_steps,
            )

    def _train_trl(
        self, chunks, epochs, batch_size, grad_accum,
        lr, weight_decay, warmup_ratio, checkpoint_every, resume_from, seed,
    ):
        from trl import SFTTrainer, SFTConfig
        from datasets import Dataset

        ds = Dataset.from_dict({"text": chunks})
        ckpt_dir = "/tmp/synapse_checkpoints"

        cfg = SFTConfig(
            output_dir=ckpt_dir,
            num_train_epochs=epochs,
            per_device_train_batch_size=batch_size,
            gradient_accumulation_steps=grad_accum,
            learning_rate=lr,
            weight_decay=weight_decay,
            warmup_ratio=warmup_ratio,
            lr_scheduler_type="cosine",
            optim="adamw_torch",
            fp16=False,
            bf16=False,
            max_grad_norm=1.0,
            logging_steps=5,
            save_steps=checkpoint_every if checkpoint_every > 0 else 999999,
            save_total_limit=2,
            seed=seed,
            report_to="none",
            dataset_text_field="text",
            max_seq_length=self.max_seq_length,
            packing=True,   # packs multiple short docs into one sequence = faster
        )

        trainer = SFTTrainer(
            model=self._model,
            tokenizer=self._tokenizer,
            train_dataset=ds,
            args=cfg,
        )
        trainer.train(resume_from_checkpoint=resume_from)

    def _train_manual(
        self, chunks, epochs, batch_size, grad_accum,
        lr, weight_decay, warmup_ratio, total_steps,
    ):
        """
        Pure-PyTorch training loop.
        Implements: cosine LR + linear warmup, gradient clipping,
        gradient accumulation, OOM recovery, memory cleanup.
        """
        import torch
        from torch.optim import AdamW

        self._model.train()
        trainable_params = [p for p in self._model.parameters() if p.requires_grad]
        optimizer = AdamW(trainable_params, lr=lr, weight_decay=weight_decay, eps=1e-8)

        warmup_steps = max(1, int(total_steps * warmup_ratio))
        step = 0
        accum_loss = 0.0
        optimizer.zero_grad()
        progress = Progress(total_steps, desc="steps")

        def get_lr(s):
            """Linear warmup then cosine decay."""
            if s < warmup_steps:
                return lr * s / warmup_steps
            progress_frac = (s - warmup_steps) / max(1, total_steps - warmup_steps)
            import math
            return lr * 0.1 + (lr - lr * 0.1) * 0.5 * (1 + math.cos(math.pi * progress_frac))

        for epoch in range(epochs):
            epoch_chunks = chunks.copy()
            random.shuffle(epoch_chunks)

            for i in range(0, len(epoch_chunks), batch_size):
                batch = epoch_chunks[i : i + batch_size]
                if not batch:
                    continue

                # Update LR
                cur_lr = get_lr(step)
                for pg in optimizer.param_groups:
                    pg["lr"] = cur_lr

                try:
                    enc = self._tokenizer(
                        batch,
                        return_tensors="pt",
                        padding=True,
                        truncation=True,
                        max_length=self.max_seq_length,
                    )
                    labels = enc["input_ids"].clone()
                    # Don't compute loss on padding tokens
                    if self._tokenizer.pad_token_id is not None:
                        labels[labels == self._tokenizer.pad_token_id] = -100

                    out = self._model(**enc, labels=labels)
                    loss = out.loss / grad_accum
                    loss.backward()
                    accum_loss += loss.item()

                except RuntimeError as e:
                    if "out of memory" in str(e).lower():
                        print(f"\n      [OOM at step {step}] Skipping batch. "
                              f"Try: batch_size=1, max_seq_length=256, mode='tiny'")
                        optimizer.zero_grad()
                        gc.collect()
                        step += 1
                        continue
                    raise

                if (step + 1) % grad_accum == 0:
                    torch.nn.utils.clip_grad_norm_(trainable_params, max_norm=1.0)
                    optimizer.step()
                    optimizer.zero_grad()
                    progress.update(1, loss=accum_loss * grad_accum)
                    accum_loss = 0.0
                    gc.collect()

                step += 1

        # Final step for any remaining accumulated gradients
        if accum_loss > 0:
            import torch
            torch.nn.utils.clip_grad_norm_(trainable_params, 1.0)
            optimizer.step()
            optimizer.zero_grad()

        progress.close()

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _save(self, output_path: str, reserve_bytes: int):
        """
        Save the trained LoRA with Synapse metadata.

        The synapse_meta block tells the injector:
          - How many weights are available
          - How much space is reserved for stego
          - Which model this was trained on (needed to load for inference)
        """
        import torch

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        # Extract only trainable LoRA parameters
        lora_state: dict = {}
        for name, param in self._model.named_parameters():
            if "lora" in name.lower() and param.requires_grad:
                lora_state[name] = param.detach().cpu().float()

        if not lora_state:
            # Fallback: save everything (PEFT merge case)
            print("      No explicit lora_ params found — saving full PEFT state dict")
            lora_state = {
                k: v.detach().cpu().float()
                for k, v in self._model.state_dict().items()
            }

        total_w = sum(v.numel() for v in lora_state.values())
        # Each stego byte requires 8 bits × 3 repetitions = 24 weights
        stego_weights_needed = reserve_bytes * 24
        capacity = max(0, (total_w // 24) - 4)   # 4 = header overhead

        if stego_weights_needed > total_w * 0.35:
            safe_max = int(total_w * 0.35 / 24)
            print(f"      ⚠  reserve_bytes={reserve_bytes} is "
                  f"{stego_weights_needed/total_w*100:.0f}% of weight space.")
            print(f"         Recommended max for this LoRA: {safe_max} bytes")

        torch.save({
            "lora_weights": lora_state,
            "synapse_meta": {
                "version":          "0.1.0",
                "mode":             self.mode,
                "rank":             self.rank,
                "model_id":         self.model_id,
                "total_weights":    total_w,
                "reserve_bytes":    reserve_bytes,
                "stego_capacity":   capacity,
                "target_modules":   self.preset.target_modules,
                "max_seq_length":   self.max_seq_length,
            },
        }, str(out))

        size_mb = out.stat().st_size / 1024 / 1024
        print(f"      File:        {size_mb:.1f} MB")
        print(f"      Parameters:  {total_w:,}")
        print(f"      Stego cap:   {capacity:,} bytes")


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def train(
    data_path: str,
    output_path: str,
    mode: Literal["tiny", "fast", "quality"] = "fast",
    **kwargs,
) -> str:
    """
    One-line training.

        from synapse.train import train
        train("./docs/", "./my.lora", mode="fast")
    """
    return SynapseTrainer(mode=mode).train(
        data_path=data_path,
        output_path=output_path,
        **kwargs,
    )
