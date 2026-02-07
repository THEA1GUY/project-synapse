import hashlib
import random
import json
import struct
import os
import zlib

class SynapseForge:
    """
    Skeptical Neural Steganography Engine.
    Hardenining for float32 precision and binary stability.
    """
    def __init__(self, passkey: str):
        # Using SHA-256 to ensure the seed is robust
        self.seed_hash = hashlib.sha256(passkey.encode()).digest()
        self.random_seed = int.from_bytes(self.seed_hash[:4], 'little')

    def _get_indices(self, total_elements, num_bits):
        random.seed(self.random_seed)
        indices = list(range(total_elements))
        random.shuffle(indices)
        return indices[:num_bits]

    def forge(self, payload_text, mask_name):
        """
        Creates a hardened .safetensors mask.
        Includes CRC32 for integrity verification.
        """
        raw_data = payload_text.encode('utf-8')
        # Add CRC32 to the end of the payload for skepticism/verification
        checksum = zlib.crc32(raw_data) & 0xffffffff
        protected_payload = raw_data + struct.pack('<I', checksum)
        
        bits = []
        for byte in protected_payload:
            for i in range(8):
                bits.append((byte >> i) & 1)
        
        num_bits = len(bits)
        # We need enough weights to avoid collision. 10x headroom.
        num_weights = max(num_bits * 10, 10000)
        
        # Use a deterministic base for weights so the mask looks 'normal'
        random.seed(self.random_seed + 1)
        weights = [random.uniform(-0.05, 0.05) for _ in range(num_weights)]
        
        indices = self._get_indices(num_weights, num_bits)
        
        # Injection with Precision Guard (using 1e6 instead of 1e7 for float32 stability)
        PRECISION = 1000000 
        for i, idx in enumerate(indices):
            val = weights[idx]
            scaled = int(val * PRECISION)
            if (scaled & 1) != bits[i]:
                # Adjust by 1 unit of precision
                scaled += 1 if bits[i] == 1 else -1
            weights[idx] = float(scaled) / PRECISION
            
        filename = f"synapse_{mask_name.lower().replace(' ', '_')}.safetensors"
        
        # Binary Safetensors construction
        weight_data = struct.pack(f'{len(weights)}f', *weights)
        header = json.dumps({
            "__metadata__": {
                "type": "synapse_v1_hardened",
                "payload_bytes": len(raw_data), # Original size
                "total_bytes": len(protected_payload) # Size with CRC
            },
            "stealth_weights": {
                "dtype": "F32",
                "shape": [len(weights)],
                "data_offsets": [0, len(weight_data)]
            }
        }).encode('utf-8')
        
        # Header must be 8-byte aligned
        header_len = len(header)
        padding = (8 - (header_len % 8)) % 8
        header += b' ' * padding
        
        header_size_bin = struct.pack('<Q', len(header))
        
        with open(filename, "wb") as f:
            f.write(header_size_bin)
            f.write(header)
            f.write(weight_data)
            
        return filename

def main():
    print("\n📟 \033[1;34mSynapse: Hardened Forge\033[0m")
    print("--------------------------------")
    
    payload = input("\n\033[1;32m[1]\033[0m Secret Data: ")
    mask = input("\033[1;32m[2]\033[0m Mask Name: ")
    key = input("\033[1;32m[3]\033[0m Passkey: ")
    
    if len(key) < 8:
        print("\n\033[1;31m[SKEPTIC ALERT]\033[0m Passkey too weak. Use 8+ characters.")
        return

    forge = SynapseForge(key)
    path = forge.forge(payload, mask)
    
    print(f"\n[+] Neural Mask Created: {path}")
    print("[+] Integrity: CRC32 checksum embedded.")

if __name__ == "__main__":
    main()
