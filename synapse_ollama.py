import hashlib
import random
import json
import struct
import os
import zlib
import subprocess

from synapse_token import SynapseTokenSystem

class SynapseUnmasker:
    def __init__(self, passkey: str):
        self.seed_hash = hashlib.sha256(passkey.encode()).digest()
        self.random_seed = int.from_bytes(self.seed_hash[:4], 'little')

    def unmask(self, filename):
        # Strip quotes if the user pasted them
        filename = filename.strip().strip('"').strip("'")
        
        if not os.path.exists(filename):
            return None, None, f"File missing: {filename}"

        try:
            with open(filename, "rb") as f:
                header_size_data = f.read(8)
                if not header_size_data or len(header_size_data) < 8:
                    return None, None, "File is empty or corrupted (Invalid Synapse Header)."
                
                header_size = struct.unpack('<Q', header_size_data)[0]
                
                header_raw = f.read(header_size)
                if len(header_raw) < header_size:
                    return None, None, "File corrupted (Incomplete Header)."
                
                header = json.loads(header_raw.decode('utf-8'))
                
                meta = header["__metadata__"]
                original_size = meta["payload_bytes"]
                total_bytes = meta["total_bytes"]
                original_filename = meta.get("original_filename", "extracted_file.bin")
                
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
                return None, None, "INTEGRITY FAILURE: Data corruption or wrong passkey."
            
            return extracted_payload, original_filename, None

        except Exception as e:
            return None, None, f"TECHNICAL ERROR: {str(e)}"

    def run_ollama(self, model, payload, query):
        print(f"\n🚀 [Synapse] Injecting Ghost Context into {model}...")
        
        # SKEPTIC: Is this actual text or binary?
        is_binary = False
        try:
            # Check for null bytes or high non-ascii density
            if b'\x00' in payload:
                is_binary = True
            context_text = payload.decode('utf-8')
            # One more check: if it's mostly gibberish
            if len([c for c in context_text if ord(c) > 127]) / len(context_text) > 0.3:
                is_binary = True
        except:
            is_binary = True

        if is_binary:
            context_text = f"[Binary Data: {len(payload)} bytes - Cannot be read as text]"
            print(f"\033[1;33m[SKEPTIC ALERT]\033[0m Payload is binary (Image/Audio).")
            print(f"Standard LLMs cannot 'see' raw bytes. Use Option 2 to reconstruct the file.")
        
        prompt = f"System: Use this hidden context for the following query. Context: {context_text}. User: {query}"
        
        print("-" * 40)
        print(f"GHOST DATA UNMASKED: {context_text[:100]}...")
        print(f"USER QUERY: {query}")
        print("-" * 40)
        
        try:
            # Force UTF-8 encoding for Windows stability
            cmd = ["ollama", "run", model, prompt]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8')
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
    token_or_key = input("[2] Passkey or SYN- Token: ").strip()
    
    # Check if it's a token or a raw key
    if token_or_key.startswith("SYN-"):
        ts = SynapseTokenSystem()
        key, err = ts.verify_token(token_or_key)
        if err:
            print(f"\n\033[1;31m[!] Token Error:\033[0m {err}")
            return
        print(f"[*] Neural Token Verified. Unmasking...")
    else:
        key = token_or_key
    
    unmasker = SynapseUnmasker(key)
    payload, original_filename, err = unmasker.unmask(file_path)
    
    if err:
        print(f"\n\033[1;31m[!] {err}\033[0m")
    else:
        print(f"\n\033[1;32m[+] SUCCESS:\033[0m Data verified and unmasked.")
        
        print("\n[Actions]")
        print("1. Bridge to Ollama (Ghost RAG)")
        print("2. Reconstruct/Download Original File")
        print("3. View as Text")
        
        choice = input("\nSelection [1-3]: ")
        
        if choice == '1':
            model = input("Ollama Model Name (e.g. llama3): ")
            query = input("Your Question: ")
            response = unmasker.run_ollama(model, payload, query)
            print(f"\n\033[1;36m[AI RESPONSE]\033[0m\n{response}")
            
        elif choice == '2':
            out_name = "reconstructed_" + os.path.basename(original_filename)
            with open(out_name, "wb") as f:
                f.write(payload)
            print(f"\n\033[1;32m[+] File Reconstructed:\033[0m {out_name}")
            
        elif choice == '3':
            try:
                print(f"\n\033[1;34m[GHOST DATA]\033[0m\n{payload.decode('utf-8')}")
            except:
                print("\n\033[1;31m[!]\033[0m Data is binary. Use 'Reconstruct' to view.")

if __name__ == "__main__":
    main()
