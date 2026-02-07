import hashlib
import secrets
import base64
import json
import time

class SynapseTokenSystem:
    """
    Neural Token System for Project Synapse.
    Generates high-entropy seeds and wraps them in signed access tokens.
    """
    def __init__(self, master_secret="synapse_master_guard"):
        self.master_secret = master_secret

    def generate_access_token(self, payload_name, expiry_hours=24):
        """Generates a high-entropy seed and a signed token string."""
        # 1. Generate the actual neural seed (the hidden passkey)
        neural_seed = secrets.token_hex(16)
        
        # 2. Create the token payload
        expiry_timestamp = int(time.time() + (expiry_hours * 3600))
        token_payload = {
            "pld": payload_name,
            "exp": expiry_timestamp,
            "seed": neural_seed
        }
        
        # 3. Sign and encode the token
        raw_json = json.dumps(token_payload).encode('utf-8')
        encoded_payload = base64.urlsafe_b64encode(raw_json).decode('utf-8')
        
        # Simple HMAC-like signature
        signature = hashlib.sha256(f"{encoded_payload}.{self.master_secret}".encode()).hexdigest()[:16]
        
        token_string = f"SYN-{encoded_payload}.{signature}"
        
        return token_string, neural_seed

    def verify_token(self, token_string):
        """Verifies a token and returns the unmasked neural seed."""
        if not token_string.startswith("SYN-"):
            return None, "Invalid Token Format"
        
        try:
            parts = token_string[4:].split('.')
            if len(parts) != 2:
                return None, "Malformed Token"
            
            encoded_payload, signature = parts
            
            # Verify Signature
            expected_sig = hashlib.sha256(f"{encoded_payload}.{self.master_secret}".encode()).hexdigest()[:16]
            if signature != expected_sig:
                return None, "Token Signature Mismatch"
            
            # Decode Payload
            payload = json.loads(base64.urlsafe_b64decode(encoded_payload).decode('utf-8'))
            
            # Check Expiry
            if time.time() > payload["exp"]:
                return None, "Token Expired"
            
            return payload["seed"], None
            
        except Exception as e:
            return None, f"Verification Error: {str(e)}"

def main():
    print("\n📟 \033[1;34mSynapse: Neural Token Lab\033[0m")
    print("--------------------------------")
    
    ts = SynapseTokenSystem()
    
    print("1. Generate New Access Token")
    print("2. Verify/Decode Token")
    
    choice = input("\nSelection [1-2]: ")
    
    if choice == "1":
        name = input("Target Payload Name: ")
        token, seed = ts.generate_access_token(name)
        print(f"\n\033[1;32m[+] TOKEN GENERATED:\033[0m {token}")
        print(f"[*] Neural Seed (Hidden): {seed}")
        print(f"[*] Expires in: 24 Hours")
        
    elif choice == "2":
        token = input("Enter SYN- Token: ")
        seed, err = ts.verify_token(token)
        if err:
            print(f"\033[1;31m[!] {err}\033[0m")
        else:
            print(f"\n\033[1;32m[+] TOKEN VALID\033[0m")
            print(f"Neural Seed Unmasked: {seed}")

if __name__ == "__main__":
    main()
