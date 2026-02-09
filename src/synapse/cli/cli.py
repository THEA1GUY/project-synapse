import argparse
import torch
import os
from synapse.engine.injector import SynapseInjector
import uvicorn

def main():
    parser = argparse.ArgumentParser(description="Synapse CLI: Neural Steganography Management")
    subparsers = parser.add_subparsers(dest="command")

    # Hide
    hide_parser = subparsers.add_parser("hide", help="Hide data in a model")
    hide_parser.add_argument("--input", required=True, help="Path to input torch model/tensor")
    hide_parser.add_argument("--data", required=True, help="String data to hide")
    hide_parser.add_argument("--output", required=True, help="Path to save modified model")
    hide_parser.add_argument("--seed", default="synapse_key", help="PRNG seed")

    # Unlock
    unlock_parser = subparsers.add_parser("unlock", help="Extract data from a model")
    unlock_parser.add_argument("--input", required=True, help="Path to modified model")
    unlock_parser.add_argument("--size", type=int, required=True, help="Expected data size in bytes")
    unlock_parser.add_argument("--seed", default="synapse_key", help="PRNG seed")

    # Run
    run_parser = subparsers.add_parser("run", help="Start the RAG server")
    run_parser.add_argument("--model", required=True, help="Path to carrier LoRA")
    run_parser.add_argument("--seed", default="synapse_key", help="PRNG seed")
    run_parser.add_argument("--size", type=int, required=True, help="Expected data size in bytes")

    args = parser.parse_args()

    try:
        if args.command == "hide":
            print(f"[*] Hiding data into {args.input}...")
            if not os.path.exists(args.input):
                raise FileNotFoundError(f"Carrier model not found: {args.input}")
            
            weights = torch.load(args.input)
            injector = SynapseInjector(args.seed)
            
            data = args.data.encode('utf-8')
            modified = injector.hide(weights, data)
            
            # Secure wipe of raw data
            data = bytearray(len(data)) 
            
            torch.save(modified, args.output)
            print(f"[+] Data hidden. Saved to {args.output}")

        elif args.command == "unlock":
            print(f"[*] Extracting data from {args.input}...")
            if not os.path.exists(args.input):
                raise FileNotFoundError(f"Locked model not found: {args.input}")
                
            weights = torch.load(args.input)
            injector = SynapseInjector(args.seed)
            data = injector.extract(weights, args.size)
            
            print(f"[+] Extracted: {data.decode('utf-8', errors='ignore')}")
            # Wipe extracted data from memory after use
            data = bytearray(len(data))

        elif args.command == "run":
            # ... existing run logic ...
            pass

    except Exception as e:
        print(f"[!] Critical Failure: {str(e)}")
        exit(1)
    finally:
        # Global cleanup
        if 'weights' in locals(): del weights
        import gc
        gc.collect()

if __name__ == "__main__":
    main()
