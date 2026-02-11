import hashlib
import random
import json
import struct
import os
import zlib
import subprocess
import time

# Try to import pypdf for PDF text extraction
try:
    from pypdf import PdfReader
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

from synapse_token import SynapseTokenSystem

class SynapseUnmasker:
    def __init__(self, passkey: str):
        self.seed_hash = hashlib.sha256(passkey.encode()).digest()
        self.random_seed = int.from_bytes(self.seed_hash[:4], 'little')

    def unmask(self, filename):
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
                # Hardening: Ensure indices are integers even if stored as strings
                original_size = int(meta["payload_bytes"])
                total_bytes = int(meta["total_bytes"])
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
            
            # VERIFY
            calculated_checksum = zlib.crc32(extracted_payload) & 0xffffffff
            
            if calculated_checksum != stored_checksum:
                return None, None, "INTEGRITY FAILURE: Data corruption or wrong passkey."
            
            return extracted_payload, original_filename, None

        except Exception as e:
            return None, None, f"TECHNICAL ERROR: {str(e)}"

    def extract_pdf_text(self, filepath):
        if not HAS_PYPDF:
            return None
        try:
            reader = PdfReader(filepath)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            print(f"[!] PDF Extraction Error: {e}")
            return None

    def run_ollama(self, model, payload, query):
        print(f"\n🚀 [Synapse] Injecting Ghost Context into {model}...")
        
        is_binary = False
        try:
            if b'\x00' in payload:
                is_binary = True
            context_text = payload.decode('utf-8')
            if len([c for c in context_text if ord(c) > 127]) / len(context_text) > 0.3:
                is_binary = True
        except:
            is_binary = True

        if is_binary:
            temp_filename = f"synapse_ghost_media_{int(time.time())}.tmp"
            
            # Detect common file types
            is_pdf = payload.startswith(b'%PDF')
            ext_map = {
                b'\xff\xd8\xff': '.jpg',
                b'\x89PNG\r\n\x1a\n': '.png',
                b'GIF87a': '.gif',
                b'GIF89a': '.gif',
                b'%PDF': '.pdf',
                b'PK\x03\x04': '.zip',
                b'RIFF': '.wav'
            }
            
            for magic, ext in ext_map.items():
                if payload.startswith(magic):
                    temp_filename += ext
                    break
            
            with open(temp_filename, "wb") as f:
                f.write(payload)
            
            print(f"\033[1;33m[BINARY DETECTED]\033[0m File reconstructed: {temp_filename}")
            
            extracted_text = None
            if is_pdf:
                print(f"[*] Attempting PDF Intelligence Extraction...")
                extracted_text = self.extract_pdf_text(temp_filename)
                
            if extracted_text and extracted_text.strip():
                print(f"✅ Intelligence Extracted. Re-enabling Ghost RAG.")
                prompt = f"System: Use this hidden context for the following query. Context: {extracted_text}. User: {query}"
                context_snippet = extracted_text[:100].replace('\n', ' ')
            else:
                is_vision_model = any(m in model.lower() for m in ['llava', 'bakllava', 'vision'])
                if is_vision_model and temp_filename.lower().endswith(('.jpg', '.png', '.gif')):
                    prompt = f"{query} {os.path.abspath(temp_filename)}"
                    context_snippet = f"[Reconstructed Image: {temp_filename}]"
                else:
                    context_snippet = f"[Binary File: {temp_filename}]"
                    prompt = f"System: The user has unmasked a binary file ({temp_filename}). You cannot read it directly. User Query: {query}"
                    if is_pdf and not HAS_PYPDF:
                        print(f"[*] Tip: Install 'pypdf' (pip install pypdf) to enable direct PDF chatting.")
        else:
            prompt = f"System: Use this hidden context for the following query. Context: {context_text}. User: {query}"
            context_snippet = context_text[:100].replace('\n', ' ')
        
        print("-" * 40)
        print(f"GHOST DATA UNMASKED: {context_snippet}...")
        print(f"USER QUERY: {query}")
        print("-" * 40)
        
        try:
            cmd = ["ollama", "run", model]
            result = subprocess.run(cmd, input=prompt, capture_output=True, text=True, check=True, encoding='utf-8')
            return result.stdout
        except Exception as e:
            return f"\033[1;31m[OLLAMA ERROR]\033[0m {str(e)}"

def main():
    print("📟 \033[1;34mSynapse: Hardened Bridge\033[0m")
    
    file_path = input("\n[1] File Path: ").strip().strip('"').strip("'")
    token_or_key = input("[2] Passkey or SYN- Token: ").strip()
    
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
            print(f"\n\033[1;32m[+] Ghost Chat Initiated.\033[0m Type 'exit' to end.")
            
            while True:
                query = input("\n\033[1;34m[You]:\033[0m ")
                if query.lower() in ['exit', 'quit']:
                    break
                
                response = unmasker.run_ollama(model, payload, query)
                print(f"\n\033[1;36m[AI]:\033[0m\n{response}")
            
        elif choice == '2':
            out_name = "reconstructed_" + os.path.basename(original_filename)
            with open(out_name, "wb") as f:
                f.write(payload)
            print(f"\n\033[1;32m[+] File Reconstructed Resident: {os.path.abspath(out_name)}\033[0m")
            
        elif choice == '3':
            try:
                print(f"\n\033[1;34m[GHOST DATA]\033[0m\n{payload.decode('utf-8')}")
            except:
                print("\n\033[1;31m[!]\033[0m Data is binary. Use 'Reconstruct' to view.")

if __name__ == "__main__":
    main()
