import sys
import os

# Ensure the 'src' directory is in the path for local execution
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
import os
import time
import subprocess
from typing import List, Optional
from synapse.core.engine_v4 import SynapseV4Engine
from synapse_token import SynapseTokenSystem

app = FastAPI(title="Senatrax Synapse Platform")

# Multi-tenant context store
VAULT_PATH = "./vault"
os.makedirs(VAULT_PATH, exist_ok=True)

class ChatRequest(BaseModel):
    token: str
    query: str
    model: str = "llama3"

@app.get("/health")
async def health():
    return {"status": "operational", "engine": "Synapse V4 (Spectral)"}

@app.post("/chat")
async def secure_chat(request: ChatRequest):
    # 1. Token Verification
    ts = SynapseTokenSystem()
    seed, err = ts.verify_token(request.token)
    if err:
        raise HTTPException(status_code=401, detail=f"Token Invalid: {err}")
    
    # 2. Extract context from the matching mask
    # For this version, we look for a .safetensors in the vault that matches the token's payload name
    try:
        # In a real system, the token payload contains the filename.
        # Here we simulate finding it.
        context = "GHOST CONTEXT: [Verified spectral payload active]"
        
        # Search vault for any safetensors
        files = [f for f in os.listdir(VAULT_PATH) if f.endswith(".safetensors")]
        if files:
            # For demo, we just use the first one if it exists
            # In production, we'd match the exact mask from the token
            mask_path = os.path.join(VAULT_PATH, files[0])
            # Logic to load and unmask would go here
            # engine = SynapseV4Engine(seed)
            # context = engine.unmask_spectral(...)
            pass

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unmasking Error: {e}")

    # 3. Local LLM Bridge
    prompt = f"System: {context}. User: {request.query}"
    try:
        cmd = ["ollama", "run", request.model, prompt]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8')
        return {"response": result.stdout, "status": "secure"}
    except Exception as e:
        return {"response": f"AI Bridge Error: {e}. (Is Ollama running?)", "status": "error"}

if __name__ == "__main__":
    import uvicorn
    print("📟 Senatrax Synapse: Platform Server Starting...")
    uvicorn.run(app, host="127.0.0.1", port=8000)
