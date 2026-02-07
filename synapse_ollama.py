import hashlib
import random
import json
import struct
import os
import zlib
import subprocess

class SynapseUnmasker:
    def __init__(self, passkey: str):
        self.seed_hash = hashlib.sha256(passkey.encode()).digest()
        self.random_seed = int.from_bytes(self.seed_hash[:4], 'little')

    def unmask(self, filename):
        # Strip quotes if the user pasted them
        filename = filename.strip().strip('"').strip("'")
        
        if not os.path.exists(filename):
            return None, f"File missing: {filename}"

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
            
            return extracted_payload, None

        except Exception as e:
            return None, f"TECHNICAL ERROR: {str(e)}"

    def run_ollama(self, model, payload, query):
        print(f"\n🚀 [Synapse] Injecting Ghost Context into {model}...")
        
        # Try to decode as text for RAG, otherwise fallback to hex snippet
        try:
            context_text = payload.decode('utf-8')
        except:
            context_text = f"[Binary Data: {len(payload)} bytes]"

        prompt = f"System: Use this hidden context for the following query. Context: {context_text}. User: {query}"
        
        print("-" * 40)
        print(f"GHOST DATA UNMASKED: {context_text[:100]}...")
        print(f"USER QUERY: {query}")
        print("-" * 40)
        
        try:
            # Use 'py' or 'python' based on platform, but here we call the ollama binary
            cmd = ["ollama", "run", model, prompt]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout
        except Exception as e:
            # SKEPTIC: Maybe the user doesn't know their model names?
            try:
                models_list = subprocess.run(["ollama", "list"], capture_output=True, text=True).stdout
                model_suggestion = f"\n\nYour available Ollama models:\n{models_list}"
            except:
                model_suggestion = ""
            
            return f"\033[1;31m[OLLAMA ERROR]\033[0m Ensure Ollama is running and model '{model}' is pulled.{model_suggestion}"

def main():
    print("📟 \033[1;34mSynapse: Hardened Bridge\033[0m")
    
    file_path = input("\n[1] File Path: ")
    key = input("[2] Passkey: ")
    
    unmasker = SynapseUnmasker(key)
    payload, err = unmasker.unmask(file_path)
    
    if err:
        print(f"\n\033[1;31m[!] {err}\033[0m")
    else:
        print(f"\n\033[1;32m[+] SUCCESS:\033[0m Data verified and unmasked.")
        
        choice = input("\nBridge to Ollama? (y/n): ").lower()
        if choice == 'y':
            model = input("Ollama Model Name (e.g. llama3): ")
            query = input("Your Question: ")
            response = unmasker.run_ollama(model, payload, query)
            print(f"\n\033[1;36m[AI RESPONSE]\033[0m\n{response}")
        else:
            try:
                print(f"GHOST DATA: {payload.decode('utf-8')}")
            except:
                print(f"GHOST DATA (Binary): {len(payload)} bytes")

if __name__ == "__main__":
    main()
