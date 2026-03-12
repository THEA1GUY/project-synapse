"""
synapse/cli.py

Command-line interface for Synapse RAG.

Commands:
    synapse train    Train a LoRA on your documents
    synapse inject   Hide data inside a LoRA
    synapse extract  Pull hidden data back out
    synapse serve    Start the API server + dashboard
    synapse forge    Create a blank carrier LoRA for testing
    synapse verify   Test the inject → extract round-trip
"""

import argparse
import sys


# ------------------------------------------------------------------
# Command handlers
# ------------------------------------------------------------------

def cmd_train(args):
    from synapse.train.trainer import SynapseTrainer
    trainer = SynapseTrainer(
        mode=args.mode,
        base_model=args.base_model,
        rank=args.rank,
        max_seq_length=args.seq_len,
    )
    trainer.train(
        data_path=args.data,
        output_path=args.output,
        reserve_bytes=args.reserve,
        epochs=args.epochs,
        batch_size=args.batch_size,
        grad_accum=args.grad_accum,
        learning_rate=args.lr,
        checkpoint_every=args.checkpoint_every,
        resume_from=args.resume,
    )


def cmd_inject(args):
    from synapse import Synapse
    app = Synapse(backend="openai", model="mock")
    app.inject(
        data=args.data,
        key=args.key,
        lora=args.lora,
        output=args.output,
    )


def cmd_extract(args):
    from synapse import Synapse
    app = Synapse(backend="openai", model="mock")
    try:
        data = app.extract(key=args.key, lora=args.lora)
        text = data.decode("utf-8", errors="ignore").strip("\x00")
        print(f"\n✓ Extracted ({len(data)} bytes):\n")
        print(text)
        if args.output:
            from pathlib import Path
            Path(args.output).write_bytes(data)
            print(f"\nSaved to: {args.output}")
    except Exception as e:
        print(f"\n✗ Failed: {e}")
        sys.exit(1)


def cmd_serve(args):
    from synapse import Synapse

    kwargs = dict(backend=args.backend, model=args.model)
    if args.api_key:
        kwargs["api_key"] = args.api_key
    if args.base_url:
        kwargs["base_url"] = args.base_url
    if args.lora:
        kwargs["lora"] = args.lora

    app = Synapse(**kwargs)

    if args.key and args.lora:
        try:
            app.unlock(key=args.key)
            print(f"[synapse] Context pre-loaded.")
        except Exception as e:
            print(f"[synapse] Warning: could not pre-unlock: {e}")

    app.serve(host=args.host, port=args.port)


def cmd_forge(args):
    """Create a blank carrier LoRA with random weights for testing."""
    import random
    import struct
    from pathlib import Path

    n = args.size * 1000
    try:
        import torch
        weights = torch.randn(n)
        torch.save(weights, args.output)
    except ImportError:
        weights = [random.gauss(0, 0.02) for _ in range(n)]
        raw = struct.pack(f"{n}f", *weights)
        Path(args.output).write_bytes(raw)

    from synapse.engine.injector import SynapseInjector
    size    = Path(args.output).stat().st_size
    cap     = SynapseInjector.capacity_bytes(n)
    print(f"\n✓ Carrier LoRA created: {args.output}")
    print(f"  Weights:       {n:,}")
    print(f"  File size:     {size:,} bytes")
    print(f"  Stego capacity: ~{cap:,} bytes")
    print(f"\n  Next: synapse inject --lora {args.output} --data <file> --key <key>")


def cmd_verify(args):
    """Test that inject → extract round-trip works correctly."""
    import random
    from synapse.engine.injector import SynapseInjector

    key     = args.key or "synapse_verify_key"
    message = args.message or "Synapse: hidden knowledge unlocked. Round-trip OK."

    print(f"\n[synapse verify]")
    print(f"  Key:     {key}")
    print(f"  Message: {message!r}")

    n       = 10_000
    weights = [random.gauss(0, 0.02) for _ in range(n)]
    inj     = SynapseInjector(key)

    try:
        modified  = inj.hide(weights, message.encode())
        extracted = inj.extract_auto(modified)
        result    = extracted.decode("utf-8", errors="ignore").strip("\x00")

        if result == message:
            print(f"\n  ✓ Encryption:     OK")
            print(f"  ✓ PRNG scatter:   OK")
            print(f"  ✓ Error correction: OK")
            print(f"  ✓ Round-trip:     OK")
            print(f"\n  [SUCCESS] Ready to use.\n")
        else:
            print(f"\n  ✗ Mismatch!")
            print(f"    Expected: {message!r}")
            print(f"    Got:      {result!r}")
            sys.exit(1)

    except Exception as e:
        print(f"\n  ✗ Error: {e}")
        sys.exit(1)


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="synapse",
        description="Synapse RAG — Neural Steganography Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  synapse forge  --size 100 --output carrier.lora
  synapse inject --lora carrier.lora --data ./secrets.md --key mypassword
  synapse verify
  synapse serve  --backend ollama --model llama3 --lora carrier.lora --key mypassword
  synapse serve  --backend openai --model gpt-4o --api-key sk-... --lora carrier.lora
  synapse train  --data ./docs/ --output trained.lora --mode fast
        """,
    )

    sub = parser.add_subparsers(dest="command", metavar="command")
    sub.required = True

    # ── train ──────────────────────────────────────────────────────────
    p = sub.add_parser("train", help="Train a LoRA on your documents")
    p.add_argument("--data",     required=True,
                   help="File or directory of documents")
    p.add_argument("--output",   required=True,
                   help="Output .lora file path")
    p.add_argument("--mode",     default="fast",
                   choices=["tiny", "fast", "quality"],
                   help="tiny=<1min  fast=2-5min  quality=15-30min  (default: fast)")
    p.add_argument("--base-model",       dest="base_model", default=None,
                   help="Override the HuggingFace model ID")
    p.add_argument("--rank",             type=int, default=None,
                   help="LoRA rank (default: set by mode)")
    p.add_argument("--seq-len",          dest="seq_len", type=int, default=512,
                   help="Max sequence length (default: 512)")
    p.add_argument("--epochs",           type=int, default=1)
    p.add_argument("--batch-size",       dest="batch_size", type=int, default=1)
    p.add_argument("--grad-accum",       dest="grad_accum", type=int, default=16)
    p.add_argument("--lr",               type=float, default=2e-4)
    p.add_argument("--reserve",          type=int, default=8192,
                   help="Bytes to reserve for stego (default: 8192)")
    p.add_argument("--checkpoint-every", dest="checkpoint_every", type=int, default=0)
    p.add_argument("--resume",           default=None)

    # ── inject ─────────────────────────────────────────────────────────
    p = sub.add_parser("inject", help="Hide data inside a LoRA file")
    p.add_argument("--lora",   required=True, help="Path to LoRA file")
    p.add_argument("--data",   required=True, help="File path or string to hide")
    p.add_argument("--key",    required=True, help="Secret key")
    p.add_argument("--output", help="Output path (default: overwrite input)")

    # ── extract ────────────────────────────────────────────────────────
    p = sub.add_parser("extract", help="Extract hidden data from a LoRA")
    p.add_argument("--lora",   required=True, help="Path to LoRA file")
    p.add_argument("--key",    required=True, help="Secret key")
    p.add_argument("--output", help="Save extracted data to file")

    # ── serve ──────────────────────────────────────────────────────────
    p = sub.add_parser("serve", help="Start the API server + dashboard")
    p.add_argument("--backend", required=True,
                   help="'openai' for any OpenAI-compatible API, 'anthropic' for Claude")
    p.add_argument("--model",    required=True,
                   help="Model name (e.g. gpt-4o, llama3, claude-sonnet-4-6)")
    p.add_argument("--api-key",  dest="api_key", default=None,
                   help="API key (or set via env var)")
    p.add_argument("--base-url", dest="base_url", default=None)
    p.add_argument("--lora",     default=None,  help="Path to LoRA file")
    p.add_argument("--key",      default=None,  help="Auto-unlock on startup")
    p.add_argument("--host",     default="0.0.0.0")
    p.add_argument("--port",     type=int, default=8000)

    # ── forge ──────────────────────────────────────────────────────────
    p = sub.add_parser("forge", help="Create a blank carrier LoRA for testing")
    p.add_argument("--size",   type=int, default=50,
                   help="Size in K weights (default: 50)")
    p.add_argument("--output", default="carrier.lora")

    # ── verify ─────────────────────────────────────────────────────────
    p = sub.add_parser("verify", help="Test inject → extract round-trip")
    p.add_argument("--key",     default=None)
    p.add_argument("--message", default=None)

    # ── Dispatch ───────────────────────────────────────────────────────
    args = parser.parse_args()
    {
        "train":   cmd_train,
        "inject":  cmd_inject,
        "extract": cmd_extract,
        "serve":   cmd_serve,
        "forge":   cmd_forge,
        "verify":  cmd_verify,
    }[args.command](args)


if __name__ == "__main__":
    main()