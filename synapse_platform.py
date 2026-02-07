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
    # If token is "LOCAL_CONTEXT", we bypass token check and use ad-hoc context (for testing/local UI)
    context = ""
    if request.token == "LOCAL_CONTEXT":
        context = request.query.split("|CONTEXT:")[1] if "|CONTEXT:" in request.query else ""
        query = request.query.split("|CONTEXT:")[0]
    else:
        ts = SynapseTokenSystem()
        seed, err = ts.verify_token(request.token)
        if err:
            raise HTTPException(status_code=401, detail=f"Token Invalid: {err}")
        
        # 2. Extract context from the matching mask
        # Real logic: Find file in vault. For demo, we use a placeholder.
        context = "GHOST CONTEXT: [Verified spectral payload active]"
        query = request.query

    # 3. Local LLM Bridge
    # Construct prompt with context
    system_prompt = f"You are a Synapse Ghost Agent. Use the following hidden context to answer the user's request. Context: {context}"
    full_prompt = f"System: {system_prompt}. User: {query}"
    
    try:
        cmd = ["ollama", "run", request.model, full_prompt]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8')
        return {"response": result.stdout, "status": "secure"}
    except Exception as e:
        return {"response": f"AI Bridge Error: {e}. Ensure Ollama is running (`ollama serve`).", "status": "error"}

@app.post("/verify")
async def verify_token(request: dict):
    token = request.get("token")
    if not token:
        raise HTTPException(status_code=400, detail="No token provided")
    
    ts = SynapseTokenSystem()
    seed, err = ts.verify_token(token)
    if err:
        return {"valid": false, "error": str(err)}
    return {"valid": true, "seed": seed}

if __name__ == "__main__":
    import uvicorn
    print("📟 Senatrax Synapse: Platform Server Starting...")
    uvicorn.run(app, host="127.0.0.1", port=8000)
