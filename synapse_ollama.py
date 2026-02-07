import hashlib
import random
import json
import struct
import os
import zlib

class SynapseUnmasker:
    def __init__(self, passkey: str):
        self.seed_hash = hashlib.sha256(passkey.encode()).digest()
        self.random_seed = int.from_bytes(self.seed_hash[:4], 'little')

    def unmask(self, filename):
        if not os.path.exists(filename):
            return None, "File missing."

        try:
            with open(filename, "rb") as f:
                header_size = struct.unpack('<Q', f.read(8))[0]
                header = json.loads(f.read(header_size).decode('utf-8'))
                
                meta = header["__metadata__"]
                original_size = meta["payload_bytes"]
                total_bytes = meta["total_bytes"]
                
                weight_shape = header["stealth_weights"]["shape"][0]
                weight_data = f.read()
                weights = struct.unpack(f'{weight_shape}f', weight_data)

            # Reconstruct indices
            num_bits = total_bytes * 8
            random.seed(self.random_seed)
            indices = list(range(len(weights)))
            random.shuffle(indices)
            target_indices = indices[:num_bits]
            
            # Extract Bits
            PRECISION = 1000000
            bits = []
            for idx in target_indices:
                val = weights[idx]
                # Floating point skepticism: round to the nearest precision unit
                scaled = int(round(val * PRECISION))
                bits.append(scaled & 1)
                
            # Convert bits to bytes
            buffer = bytearray()
            for i in range(0, len(bits), 8):
                byte = 0
                for j in range(8):
                    if bits[i + j]: byte |= (1 << j)
                buffer.append(byte)
            
            # Split payload and Checksum
            extracted_payload = bytes(buffer[:original_size])
            stored_checksum = struct.unpack('<I', buffer[original_size:original_size+4])[0]
            
            # VERIFY (Skeptical Check)
            calculated_checksum = zlib.crc32(extracted_payload) & 0xffffffff
            
            if calculated_checksum != stored_checksum:
                return None, "INTEGRITY FAILURE: Data corruption or wrong passkey."
            
            return extracted_payload.decode('utf-8', errors='ignore'), None

        except Exception as e:
            return None, f"TECHNICAL ERROR: {str(e)}"

def main():
    print("📟 \033[1;34mSynapse: Hardened Bridge\033[0m")
    
    file_path = input("\n[1] File Path: ")
    key = input("[2] Passkey: ")
    
    unmasker = SynapseUnmasker(key)
    data, err = unmasker.unmask(file_path)
    
    if err:
        print(f"\n\033[1;31m[!] {err}\033[0m")
    else:
        print(f"\n\033[1;32m[+] SUCCESS:\033[0m Data verified and unmasked.")
        print(f"GHOST DATA: {data}")

if __name__ == "__main__":
    main()
