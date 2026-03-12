import random
import struct
import os
from synapse import Synapse

def create_carrier(filename="test.lora", size_k=50):
    """Creates a fake/blank LoRA model with random float weights for testing using torch."""
    import torch
    print(f"[*] Creating a mock {size_k}K weight LoRA carrier using torch...")
    n = size_k * 1000
    weights = torch.randn(n)
    
    torch.save(weights, filename)
    print(f"[+] Mock LoRA saved to '{filename}'")

def run_test():
    # 1. Create the carrier LoRA file
    carrier_lora = "test.lora"
    injected_lora = "test_injected.lora"
    secret_key = "my_secure_password"
    secret_message = "The launch codes are: ALPHA-9-TANGO. Keep this strictly confidential."
    
    create_carrier(carrier_lora, size_k=100)

    # 2. Instantiating the Synapse App (mock backend for testing)
    print("\n[*] Initializing Synapse (Mock Backend)...")
    app = Synapse(backend="openai", model="mock", api_key="sk-mock")

    # 3. Injecting the secret payload into the LoRA
    print(f"\n[*] Injecting the payload into '{carrier_lora}'...")
    app.inject(
        data=secret_message,
        key=secret_key,
        lora=carrier_lora,
        output=injected_lora
    )

    # 4. Extracting the data back out using the same key
    print(f"\n[*] Extracting payload from '{injected_lora}' using the key '{secret_key}'...")
    extracted_bytes = app.extract(key=secret_key, lora=injected_lora)
    extracted_text = extracted_bytes.decode('utf-8', errors='ignore').strip('\x00')
    
    print("\n------------------------------")
    print(f"Original Data : {secret_message}")
    print(f"Extracted Data: {extracted_text}")
    print("------------------------------")
    
    # Assert they match
    if secret_message == extracted_text:
        print("\n[SUCCESS] Pipeline working flawlessly! Data injected and extracted successfully.")
    else:
        print("\n[FAILURE] extraction mismatch!")

    # 5. Testing wrong key rejection
    from synapse.engine.injector import SynapseInjector
    import struct
    import torch

    weights = []
    # Note: Torch objects saved natively just load as tensor if torch.randn saved directly
    weights_obj = torch.load(injected_lora, map_location='cpu', weights_only=False)
    if isinstance(weights_obj, dict) and 'lora_weights' in weights_obj:
        for v in weights_obj['lora_weights'].values():
            weights.extend(v.view(-1).float().tolist())
    else:
        weights = weights_obj.view(-1).float().tolist()

    try:
        bad = SynapseInjector('wrongpassword').extract_auto(weights)
        print('FAIL — should have rejected wrong key')
    except ValueError as e:
        print('✓ Wrong key correctly rejected:', str(e)[:60])

if __name__ == "__main__":
    run_test()
