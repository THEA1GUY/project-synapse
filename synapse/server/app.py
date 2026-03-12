"""
synapse/server/app.py

FastAPI application.

Endpoints:
  GET  /              → Dashboard UI
  GET  /health        → Backend health check
  POST /query         → Query (with optional key)
  POST /unlock        → Pre-unlock a key (caches context)
  POST /lock          → Clear in-memory context (lock)
  POST /inject        → Inject payload into LoRA via API
  GET  /status        → Current server state
  GET  /docs          → Swagger UI (automatic)
"""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

if TYPE_CHECKING:
    from synapse.core import Synapse


# ------------------------------------------------------------------
# Request / Response Models
# ------------------------------------------------------------------

class QueryRequest(BaseModel):
    prompt: str
    key: Optional[str] = None
    lora: Optional[str] = None
    api_key: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "What are the launch codes?",
                "key": "my_secret_key"
            }
        }


class QueryResponse(BaseModel):
    response: str
    context_used: bool
    unlocked: bool
    chunks_retrieved: int


class UnlockRequest(BaseModel):
    key: str
    lora: Optional[str] = None


class InjectRequest(BaseModel):
    lora: str
    data: str
    key: str
    output: Optional[str] = None


class ConfigRequest(BaseModel):
    backend: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None


class StatusResponse(BaseModel):
    backend: str
    model: str
    unlocked: bool
    chunk_count: int
    lora_loaded: Optional[str]


# ------------------------------------------------------------------
# App factory
# ------------------------------------------------------------------

def create_app(synapse: "Synapse") -> FastAPI:
    app = FastAPI(
        title="Synapse RAG",
        description=(
            "Neural Steganography API. "
            "Hide knowledge inside LoRA models. Unlock it with a key."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/dashboard.html", response_class=HTMLResponse, include_in_schema=False)
    async def dashboard():
        html_path = Path(__file__).parent / "dashboard.html"
        return HTMLResponse(content=html_path.read_text())

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    @app.get("/health", tags=["System"])
    async def health():
        """Check backend connectivity."""
        result = synapse._backend.health_check()
        return {
            "synapse": "ok",
            "backend": synapse.backend_name,
            "model": synapse.model,
            "backend_ok": result["ok"],
            "backend_detail": result["detail"],
        }

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @app.get("/status", response_model=StatusResponse, tags=["System"])
    async def status():
        """Current server state."""
        return StatusResponse(
            backend=synapse.backend_name,
            model=synapse._backend.model,
            unlocked=synapse._retrieval is not None,
            chunk_count=synapse._retrieval.chunk_count if synapse._retrieval else 0,
            lora_loaded=synapse.lora_path,
        )

    @app.post("/config", tags=["System"])
    async def configure(request: ConfigRequest):
        """Update backend settings at runtime."""
        try:
            synapse.configure(
                backend=request.backend,
                model=request.model,
                api_key=request.api_key,
                base_url=request.base_url,
            )
            return {"ok": True, "message": "Configuration updated."}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    # ------------------------------------------------------------------
    # Unlock
    # ------------------------------------------------------------------

    @app.post("/unlock", tags=["Synapse"])
    async def unlock(request: UnlockRequest):
        """
        Pre-unlock a LoRA payload into memory.
        After this, queries will use the hidden knowledge without needing the key each time.
        """
        try:
            synapse.unlock(key=request.key, lora=request.lora)
            return {
                "ok": True,
                "message": "Context unlocked.",
                "chunk_count": synapse._retrieval.chunk_count if synapse._retrieval else 0,
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    # ------------------------------------------------------------------
    # Lock
    # ------------------------------------------------------------------

    @app.post("/lock", tags=["Synapse"])
    async def lock():
        """
        Clear the in-memory context, reverting the model to normal chatbot mode.
        The LoRA file remains untouched. Call /unlock to restore context.
        """
        synapse._retrieval = None
        return {"ok": True, "message": "Context cleared. Model is now locked."}

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    @app.post("/query", response_model=QueryResponse, tags=["Synapse"])
    async def query(request: QueryRequest):
        """
        Query the model.

        - Without a key: acts as a normal chatbot.
        - With a key: unlocks hidden context from the LoRA and uses it to answer.
        """
        try:
            result = synapse.query(
                prompt=request.prompt,
                key=request.key,
                lora=request.lora,
            )
            return QueryResponse(
                response=result["response"],
                context_used=result["context_used"],
                unlocked=result["unlocked"],
                chunks_retrieved=len(result.get("chunks", [])),
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/stream", tags=["Synapse"])
    async def stream_query(request: QueryRequest):
        """
        Streaming version of /query.
        Returns a Server-Sent Events (SSE) stream of tokens.
        """
        try:
            # 1. Unlock context if key provided and not already unlocked
            if request.key and not synapse._retrieval:
                try:
                    synapse.unlock(key=request.key, lora=request.lora)
                except Exception:
                    pass # Invalid keys will just result in no context

            # 2. Get RAG context
            chunks = []
            if synapse._retrieval:
                chunks = synapse._retrieval.retrieve(request.prompt)
            
            # 3. Build augmented prompt
            from synapse.core import Synapse
            augmented = synapse._build_prompt(request.prompt, chunks)

            # 4. Define the generator
            from fastapi.responses import StreamingResponse
            def generate():
                import json
                try:
                    for chunk in synapse._backend.stream(augmented):
                        # Use JSON encoding to handle newlines safely in SSE
                        yield f"data: {json.dumps({'content': chunk})}\n\n"
                    yield "data: [DONE]\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"

            return StreamingResponse(generate(), media_type="text/event-stream")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ------------------------------------------------------------------
    # Inject
    # ------------------------------------------------------------------

    @app.post("/inject", tags=["Synapse"])
    async def inject(request: InjectRequest):
        """
        Inject a payload into a LoRA file via the API.
        The data field can be a file path or raw text.
        """
        try:
            output_path = synapse.inject(
                data=request.data,
                key=request.key,
                lora=request.lora,
                output=request.output,
            )
            return {"ok": True, "output": output_path}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    return app
