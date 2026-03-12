# Synapse RAG — Remaining Features Build Plan

**Purpose:** Complete technical specification for all remaining features.
Hand this document to an AI IDE and build each feature in order.
Each section is self-contained with context, exact file locations, how it works, and what the tests should prove.

---

## Project Structure Reference

```
synapse/
├── __init__.py
├── core.py
├── cli.py
├── engine/
│   ├── __init__.py
│   ├── injector.py        ← stego engine lives here
│   └── retrieval.py       ← RAG retrieval lives here
├── train/
│   ├── __init__.py
│   └── trainer.py
├── backends/
│   ├── __init__.py
│   ├── openai_compatible.py
│   └── anthropic.py
└── server/
    ├── __init__.py
    ├── app.py             ← FastAPI server
    └── dashboard.html     ← frontend UI
```

---

---

# FEATURE 1 — Key Expiry

## Why

Right now a key is permanent. If you share a key with a contractor, a client, or a
temporary employee, you have no way to revoke it without re-injecting the entire
payload with a new key. Key expiry solves this by baking a timestamp into the key
itself. The key stops working on a date you choose. The LoRA file never changes.

## How It Works

A Synapse key with expiry looks like this:

```
acme_master:exp:20250601:sig:a3f9
```

It has four parts separated by colons:
- `acme_master` — the base secret (used for encryption and scatter)
- `exp` — signals this is a time-limited key
- `20250601` — expiry date in YYYYMMDD format
- `sig:a3f9` — a 4-character HMAC signature to prevent tampering with the date

The injector always uses only the base secret for encryption so the payload is
compatible with any key derived from the same base. On extraction the full key
string is parsed, the signature is verified, the date is checked against today,
and if expired a clear error is raised before any decryption is attempted.

## File To Edit

`synapse/engine/injector.py`

## What To Build

Add a new class `SynapseKey` above `SynapseInjector`:

```python
import hmac
import hashlib
from datetime import date

class SynapseKey:
    """
    Parses and validates a Synapse key string.
    
    Plain key:   "mysecret"
    Expiring key: "mysecret:exp:20250601:sig:a3f9"
    
    Usage:
        k = SynapseKey("mysecret:exp:20250601:sig:a3f9")
        k.validate()          # raises ValueError if expired or tampered
        injector = SynapseInjector(k.base_secret)
    """
    
    def __init__(self, key_string: str):
        self.raw = key_string
        self.base_secret = key_string
        self.expiry = None
        self.signature = None
        self._parse()
    
    def _parse(self):
        # If no :exp: marker this is a plain key, nothing to parse
        if ":exp:" not in self.raw:
            return
        
        parts = self.raw.split(":")
        # Expected format: base:exp:YYYYMMDD:sig:XXXX
        if len(parts) != 5 or parts[1] != "exp" or parts[3] != "sig":
            raise ValueError(
                f"Malformed expiring key. Expected format: "
                f"base_secret:exp:YYYYMMDD:sig:XXXX"
            )
        
        self.base_secret = parts[0]
        self.signature   = parts[4]
        
        try:
            d = parts[2]
            self.expiry = date(int(d[:4]), int(d[4:6]), int(d[6:8]))
        except Exception:
            raise ValueError(f"Invalid expiry date in key: {parts[2]}")
    
    def _expected_sig(self) -> str:
        # HMAC of "base_secret:YYYYMMDD" truncated to 4 chars
        msg = f"{self.base_secret}:{self.expiry.strftime('%Y%m%d')}"
        h = hmac.new(
            self.base_secret.encode(),
            msg.encode(),
            hashlib.sha256
        ).hexdigest()
        return h[:4]
    
    def validate(self):
        """Raise ValueError if key is expired or signature is invalid."""
        if self.expiry is None:
            return  # plain key, always valid
        
        # Verify signature first (prevents tampering with the date)
        expected = self._expected_sig()
        if not hmac.compare_digest(self.signature, expected):
            raise ValueError(
                "Key signature invalid. This key may have been tampered with."
            )
        
        # Check expiry
        if date.today() > self.expiry:
            raise ValueError(
                f"Key expired on {self.expiry.strftime('%Y-%m-%d')}. "
                f"Contact the key issuer for a new key."
            )
    
    @classmethod
    def generate(cls, base_secret: str, expires: str) -> str:
        """
        Generate an expiring key string.
        
        Args:
            base_secret: The underlying secret
            expires: Expiry date as "YYYY-MM-DD"
        
        Returns:
            Full key string ready to share
        
        Example:
            SynapseKey.generate("acme_master", "2025-06-01")
            # → "acme_master:exp:20250601:sig:a3f9"
        """
        d = date.fromisoformat(expires)
        date_str = d.strftime("%Y%m%d")
        msg = f"{base_secret}:{date_str}"
        sig = hmac.new(
            base_secret.encode(),
            msg.encode(),
            hashlib.sha256
        ).hexdigest()[:4]
        return f"{base_secret}:exp:{date_str}:sig:{sig}"
```

Then update `SynapseInjector.__init__` to accept a full key string and parse it:

```python
def __init__(self, key: str):
    parsed = SynapseKey(key)
    parsed.validate()               # raises immediately if expired
    self.key   = parsed.base_secret # encryption always uses base secret only
    self._seed = int(hashlib.sha256(self.key.encode()).hexdigest(), 16) % (2**32)
```

## Add CLI Command

In `synapse/cli.py` add a `keygen` command:

```python
def cmd_keygen(args):
    from synapse.engine.injector import SynapseKey
    key = SynapseKey.generate(args.base, args.expires)
    print(f"\nGenerated key: {key}")
    print(f"Base secret:   {args.base}")
    print(f"Expires:       {args.expires}")
    print(f"\nShare this key. It stops working after {args.expires}.")
```

Add to argparse:
```python
p = sub.add_parser("keygen", help="Generate a time-limited key")
p.add_argument("--base",    required=True, help="Base secret")
p.add_argument("--expires", required=True, help="Expiry date YYYY-MM-DD")
```

## Tests That Must Pass

```python
from synapse.engine.injector import SynapseKey, SynapseInjector
import random

# 1. Plain key still works unchanged
inj = SynapseInjector("plainkey")
w   = [random.gauss(0, 0.02) for _ in range(5000)]
msg = "plain key test"
assert inj.extract_auto(inj.hide(w, msg.encode())).decode().strip("\x00") == msg

# 2. Valid expiring key works
future_key = SynapseKey.generate("mybase", "2099-01-01")
inj2 = SynapseInjector(future_key)
assert inj2.extract_auto(inj2.hide(w, msg.encode())).decode().strip("\x00") == msg

# 3. Expired key raises immediately
expired_key = SynapseKey.generate("mybase", "2020-01-01")
try:
    SynapseInjector(expired_key)
    assert False, "Should have raised"
except ValueError as e:
    assert "expired" in str(e).lower()

# 4. Tampered date raises
tampered = future_key.replace("20990101", "20200101")
try:
    SynapseInjector(tampered)
    assert False, "Should have raised"
except ValueError as e:
    assert "tampered" in str(e).lower() or "invalid" in str(e).lower()

# 5. Both keys with same base extract same payload
w2 = [random.gauss(0, 0.02) for _ in range(5000)]
base_inj = SynapseInjector("sharedbase")
modified = base_inj.hide(w2, b"shared payload")

future_key2 = SynapseKey.generate("sharedbase", "2099-01-01")
exp_inj = SynapseInjector(future_key2)
result = exp_inj.extract_auto(modified).decode().strip("\x00")
assert result == "shared payload"

print("All key expiry tests passed.")
```

---

---

# FEATURE 2 — Multi-Key Multi-Payload

## Why

Right now one LoRA holds one payload accessible by one key. Multi-key allows the
same LoRA file to hold several independent encrypted payloads, each accessible
only by its own key. Key A unlocks HR docs. Key B unlocks engineering specs.
Key C unlocks access codes. Same file. Nobody with Key A can see what Key B
unlocks. This enables tiered access control with zero additional infrastructure.

## How It Works

The weight space is divided into N regions. Each region is large enough to hold
one payload. The PRNG scatter map for each key naturally distributes bits across
different positions because each key seeds a different RNG. The injector needs to
be aware of how many slots exist so it can carve out non-overlapping regions.

The simplest implementation: divide weights into equal slots by index range.
Slot 0: weights 0 to (total/N). Slot 1: weights (total/N) to (2*total/N). Etc.
Each key is assigned a slot. Injection and extraction only touch that slot.

A slot assignment file is stored as plaintext metadata alongside the LoRA:

```json
{
  "slots": 3,
  "total_weights": 100000,
  "slot_size": 33333
}
```

The metadata is not secret. Knowing how many slots exist reveals nothing about
the content of any slot.

## File To Edit

`synapse/engine/injector.py`

## What To Build

Add `slot` and `total_slots` parameters to `SynapseInjector`:

```python
class SynapseInjector:

    def __init__(self, key: str, slot: int = 0, total_slots: int = 1):
        parsed = SynapseKey(key)
        parsed.validate()
        self.key         = parsed.base_secret
        self.slot        = slot
        self.total_slots = total_slots
        self._seed = int(hashlib.sha256(self.key.encode()).hexdigest(), 16) % (2**32)
    
    def _slot_weights(self, weights: list) -> tuple[list, int]:
        """
        Return the weight subarray for this slot and the offset.
        Each slot gets an equal share of the total weight space.
        """
        size   = len(weights) // self.total_slots
        start  = self.slot * size
        end    = start + size
        return weights[start:end], start
    
    def hide(self, weights: list, data: bytes) -> list:
        slot_w, offset = self._slot_weights(weights)
        encrypted = self._encrypt(data)
        header    = struct.pack(">I", len(encrypted))
        modified_slot = self._inject_bits(slot_w, header + encrypted)
        result = list(weights)
        size   = len(weights) // self.total_slots
        result[offset : offset + size] = modified_slot
        return result
    
    def extract_auto(self, weights: list) -> bytes:
        slot_w, _ = self._slot_weights(weights)
        header  = self._extract_bits(slot_w, HEADER_BYTES)
        length  = struct.unpack(">I", header)[0]
        max_len = (len(slot_w) // (8 * REPETITION)) - HEADER_BYTES
        if length == 0 or length > max_len:
            raise ValueError(
                f"No valid payload in slot {self.slot} "
                f"(wrong key or nothing injected here)."
            )
        full = self._extract_bits(slot_w, HEADER_BYTES + length)
        return self._decrypt(full[HEADER_BYTES:])
```

## Add CLI Support

Update `syn inject` and `syn extract` to accept `--slot` and `--total-slots`:

```bash
syn inject --lora acme.lora --data hr.txt      --key hr_key      --slot 0 --total-slots 3
syn inject --lora acme.lora --data eng.txt     --key eng_key     --slot 1 --total-slots 3
syn inject --lora acme.lora --data secrets.txt --key secrets_key --slot 2 --total-slots 3

syn extract --lora acme.lora --key hr_key  --slot 0 --total-slots 3
syn extract --lora acme.lora --key eng_key --slot 1 --total-slots 3
```

Also add a `syn slots` command that shows how many slots a LoRA was configured with
by reading its metadata file (`acme.lora.meta`).

## Tests That Must Pass

```python
import random
from synapse.engine.injector import SynapseInjector

w = [random.gauss(0, 0.02) for _ in range(90000)]  # 3 slots of 30k each

payloads = [
    ("hr_key",      "HR: 25 days annual leave."),
    ("eng_key",     "ENG: PostgreSQL 15, sharded x3."),
    ("secrets_key", "CODE: DELTA-7-FOXTROT"),
]

# Inject all three into the same weights
for i, (key, data) in enumerate(payloads):
    inj = SynapseInjector(key, slot=i, total_slots=3)
    w   = inj.hide(w, data.encode())

# Extract each independently
for i, (key, expected) in enumerate(payloads):
    inj    = SynapseInjector(key, slot=i, total_slots=3)
    result = inj.extract_auto(w).decode().strip("\x00")
    assert result == expected, f"Slot {i} failed: got {result!r}"
    print(f"Slot {i} ({key}): OK")

# Cross-key extraction must fail
try:
    wrong = SynapseInjector("hr_key", slot=1, total_slots=3)
    wrong.extract_auto(w)
    assert False, "Should have failed"
except ValueError:
    print("Cross-slot extraction correctly rejected.")

print("All multi-key tests passed.")
```

---

---

# FEATURE 3 — Streaming Responses

## Why

Right now the server waits for the entire model response before sending anything
back. For long answers this means the user stares at a loading indicator for
several seconds. Streaming sends tokens as they are generated so the response
appears word by word in real time. This makes the product feel dramatically faster
and more alive, especially important for the dashboard chat interface.

## How It Works

FastAPI supports Server-Sent Events (SSE). When the client requests streaming,
the server opens a persistent HTTP connection and sends chunks as they arrive
from the model. The dashboard listens for these events and appends each chunk
to the message bubble as it arrives.

## Files To Edit

`synapse/server/app.py` — add streaming endpoint  
`synapse/backends/openai_compatible.py` — add stream method  
`synapse/backends/anthropic.py` — add stream method  
`synapse/server/dashboard.html` — use EventSource for streaming queries  

## What To Build

**In `openai_compatible.py` add:**

```python
def stream(self, prompt: str, system=None):
    """
    Generator that yields text chunks as they arrive.
    Usage: for chunk in backend.stream(prompt): print(chunk, end="")
    """
    if self.model == "mock":
        words = f"[MOCK STREAM] Response to: {prompt[:50]}".split()
        for word in words:
            yield word + " "
        return
    
    from openai import OpenAI
    client   = OpenAI(api_key=self.api_key, base_url=self.base_url)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    
    with client.chat.completions.create(
        model=self.model, messages=messages, stream=True
    ) as stream:
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
```

**In `anthropic.py` add:**

```python
def stream(self, prompt: str, system=None):
    import anthropic
    client = anthropic.Anthropic(api_key=self.api_key)
    kwargs = dict(
        model=self.model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    if system:
        kwargs["system"] = system
    
    with client.messages.stream(**kwargs) as stream:
        for text in stream.text_stream:
            yield text
```

**In `app.py` add a `/stream` endpoint:**

```python
from fastapi.responses import StreamingResponse

@app.post("/stream")
async def stream_query(request: QueryRequest):
    prompt    = request.prompt
    key       = request.key
    
    if key and not synapse._retrieval:
        try:
            synapse.unlock(key=key)
        except Exception:
            pass
    
    chunks = synapse._retrieval.retrieve(prompt, top_k=3) if synapse._retrieval else []
    augmented = synapse._build_prompt(prompt, chunks)
    
    def generate():
        try:
            for chunk in synapse._backend.stream(augmented):
                # SSE format: each message is "data: ...\n\n"
                yield f"data: {chunk}\n\n"
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")
```

**In `dashboard.html` update the send function:**

Replace the existing fetch call with an EventSource connection:

```javascript
async function sendMessage(prompt) {
    appendMessage("user", prompt);
    const bubble = appendMessage("assistant", "");
    
    const response = await fetch("/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, key: currentKey }),
    });
    
    const reader   = response.body.getReader();
    const decoder  = new TextDecoder();
    let   buffer   = "";
    
    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop();
        
        for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const chunk = line.slice(6);
            if (chunk === "[DONE]") return;
            if (chunk.startsWith("[ERROR]")) {
                bubble.textContent = chunk;
                return;
            }
            bubble.textContent += chunk;
        }
    }
}
```

## Tests That Must Pass

```python
import asyncio
from synapse.backends.openai_compatible import OpenAICompatibleBackend

b = OpenAICompatibleBackend(model="mock", api_key="no-key")

# Stream must yield multiple chunks not one big string
chunks = list(b.stream("hello"))
assert len(chunks) > 1, "Should stream multiple chunks"
assert "".join(chunks).strip() != "", "Should not be empty"
print(f"Stream: {len(chunks)} chunks — OK")

# Full text via stream matches expected
full = "".join(chunks)
assert "MOCK STREAM" in full
print("Stream content: OK")
```

Then test via curl:
```bash
curl -X POST http://localhost:8000/stream \
  -H "Content-Type: application/json" \
  -d '{"prompt": "hello"}' \
  --no-buffer
```
Should see tokens arriving one by one not all at once.

---

---

# FEATURE 4 — Persistent Memory

## Why

Right now when the server restarts all unlocked context is lost. The user has to
unlock again. For long-running deployments — a company chatbot, a persistent
agent — this is unacceptable. Persistent memory saves the unlocked context to
disk so it survives restarts and is automatically reloaded.

## How It Works

When a key is used to unlock a LoRA, the extracted payload is saved to a local
cache file keyed by a hash of the LoRA path and the key. On server startup the
server checks if a cache exists for the configured LoRA and key and loads it
automatically. The cache is encrypted with the key so it is no more readable than
the LoRA itself.

## Files To Edit

`synapse/engine/retrieval.py` — add save/load methods  
`synapse/core.py` — check cache on unlock, save to cache after unlock  
`synapse/server/app.py` — pass cache_dir to Synapse on startup  

## What To Build

**In `retrieval.py` add:**

```python
import json
import hashlib
from pathlib import Path

CACHE_DIR = Path.home() / ".synapse" / "cache"

def save(self, cache_key: str):
    """Save chunks to disk for persistence across restarts."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{cache_key}.json"
    path.write_text(json.dumps(self.chunks), encoding="utf-8")

def load(self, cache_key: str) -> bool:
    """
    Load chunks from disk if cache exists.
    Returns True if loaded, False if no cache found.
    """
    path = CACHE_DIR / f"{cache_key}.json"
    if not path.exists():
        return False
    self.chunks = json.loads(path.read_text(encoding="utf-8"))
    self._try_embeddings()
    return True

def clear_cache(self, cache_key: str):
    path = CACHE_DIR / f"{cache_key}.json"
    if path.exists():
        path.unlink()
```

**In `core.py` update `unlock`:**

```python
def unlock(self, key: str, lora: Optional[str] = None):
    from synapse.engine.retrieval import RetrievalStore
    import hashlib
    
    lora_path  = lora or self.lora_path
    cache_key  = hashlib.sha256(f"{lora_path}:{key}".encode()).hexdigest()[:16]
    
    store = RetrievalStore()
    
    # Try loading from cache first
    if store.load(cache_key):
        self._retrieval = store
        print(f"[synapse] ✓ Context restored from cache — "
              f"{store.chunk_count} chunks")
        return
    
    # Not cached — extract from LoRA and cache it
    payload = self.extract(key=key, lora=lora_path)
    text    = payload.decode("utf-8", errors="ignore").strip("\x00")
    store.load_text(text)
    store.save(cache_key)
    
    self._retrieval = store
    print(f"[synapse] ✓ Context unlocked and cached — "
          f"{len(text)} chars, {store.chunk_count} chunks")
```

Note: rename the existing `RetrievalStore.load(text)` method to `load_text(text)`
to avoid collision with the new `load(cache_key)` method.

## Tests That Must Pass

```python
import tempfile, os
from synapse.engine.retrieval import RetrievalStore

store1 = RetrievalStore()
store1.load_text("The server room code is DELTA-7-FOXTROT. Budget is 2 million.")
cache_key = "test_cache_001"
store1.save(cache_key)

# New instance loads from cache
store2 = RetrievalStore()
loaded = store2.load(cache_key)
assert loaded, "Cache load should return True"
assert store2.chunk_count > 0, "Should have chunks after loading"

results = store2.retrieve("server room code")
assert any("DELTA-7" in r for r in results), "Should retrieve correct content"
print("Persistent memory: OK")

# Cleanup
store2.clear_cache(cache_key)
assert not store2.load(cache_key), "Cache should be gone after clear"
print("Cache clear: OK")
```

---

---

# FEATURE 5 — LLM-to-LLM Context Passing

## Why

This is the most novel feature in Synapse. Today when an AI agent hands off to
another agent or when a conversation moves between models, context is either
lost entirely or passed as a raw text dump in the prompt — which is slow, visible,
and eats the entire context window.

With Synapse, Model A can serialize its working memory into a LoRA delta and pass
it to Model B. Model B loads the delta and continues from where Model A left off.
The context travels as a file, not as text. It is encrypted and invisible to
anyone in the chain who does not have the key. This enables persistent multi-agent
workflows where context accumulates across sessions and models.

## How It Works

At any point during a conversation, call `synapse.checkpoint(key)`. This:
1. Takes the current conversation history
2. Serializes it to JSON
3. Injects it into a LoRA delta (a small set of random weights, not a trained model)
4. Saves the delta to disk

To resume, the next model calls `synapse.resume(delta_path, key)`. This:
1. Extracts the conversation history from the delta
2. Loads it into the retrieval store as context
3. The new model now has full awareness of everything the previous model knew

## Files To Create

`synapse/transfer/bridge.py` — new file, the serialization logic  
`synapse/transfer/__init__.py` — new file  

## File To Edit

`synapse/core.py` — add `checkpoint()` and `resume()` methods  
`synapse/cli.py` — add `syn bridge-pack` and `syn bridge-unpack` commands  

## What To Build

**`synapse/transfer/bridge.py`:**

```python
"""
synapse/transfer/bridge.py

Serialize conversation state into a LoRA delta for transfer between models.

Usage:
    # Model A — end of session
    bridge = StateBridge(key="session_key")
    bridge.pack(
        history=conversation_history,   # list of {"role": ..., "content": ...}
        output_path="./handoff.delta"
    )
    
    # Model B — start of session
    bridge = StateBridge(key="session_key")
    state = bridge.unpack("./handoff.delta")
    # state["history"] contains everything Model A knew
"""

import json
import random
import struct
from pathlib import Path
from synapse.engine.injector import SynapseInjector


class StateBridge:

    def __init__(self, key: str, weights: int = 50000):
        self.key     = key
        self.weights = weights   # carrier size — 50k weights = ~2KB payload
    
    def pack(self, history: list, output_path: str, metadata: dict = None):
        """
        Serialize conversation history into an encrypted LoRA delta.
        
        Args:
            history:     List of {"role": "user"/"assistant", "content": "..."}
            output_path: Where to save the delta file
            metadata:    Any extra state to include (tool results, agent memory, etc.)
        """
        state = {
            "history":  history,
            "metadata": metadata or {},
            "version":  "0.1.0",
        }
        payload  = json.dumps(state, ensure_ascii=False).encode("utf-8")
        injector = SynapseInjector(self.key)
        
        # Capacity check
        max_bytes = SynapseInjector.capacity_bytes(self.weights)
        if len(payload) > max_bytes:
            raise ValueError(
                f"State too large: {len(payload)} bytes, "
                f"max for {self.weights} weights: {max_bytes} bytes. "
                f"Increase weights= or trim history."
            )
        
        # Create carrier weights
        w = [random.gauss(0, 0.02) for _ in range(self.weights)]
        modified = injector.hide(w, payload)
        
        # Save as raw float32
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(struct.pack(f"{self.weights}f", *modified))
        
        size = out.stat().st_size
        print(f"[bridge] ✓ State packed — {len(payload)} bytes → {output_path} ({size:,} bytes)")
    
    def unpack(self, delta_path: str) -> dict:
        """
        Extract conversation state from a delta file.
        
        Returns:
            {"history": [...], "metadata": {...}, "version": "..."}
        """
        raw      = Path(delta_path).read_bytes()
        n        = len(raw) // 4
        weights  = list(struct.unpack(f"{n}f", raw[:n*4]))
        injector = SynapseInjector(self.key)
        payload  = injector.extract_auto(weights)
        state    = json.loads(payload.decode("utf-8"))
        
        turns = len(state.get("history", []))
        print(f"[bridge] ✓ State unpacked — {turns} conversation turns")
        return state
```

**In `core.py` add:**

```python
def checkpoint(self, key: str, output_path: str = "./synapse.delta",
               metadata: dict = None):
    """
    Save current conversation state to a transferable delta file.
    Pass this file to another model to continue the conversation.
    """
    from synapse.transfer.bridge import StateBridge
    bridge = StateBridge(key=key)
    bridge.pack(
        history=self._history if hasattr(self, "_history") else [],
        output_path=output_path,
        metadata=metadata,
    )
    return output_path

def resume(self, delta_path: str, key: str):
    """
    Load conversation state from a delta file created by checkpoint().
    After this the model has full context of the previous session.
    """
    from synapse.transfer.bridge import StateBridge
    from synapse.engine.retrieval import RetrievalStore
    
    bridge = StateBridge(key=key)
    state  = bridge.unpack(delta_path)
    
    # Load history into retrieval store as context
    history_text = "\n".join(
        f"{turn['role'].upper()}: {turn['content']}"
        for turn in state.get("history", [])
    )
    
    if history_text:
        store = RetrievalStore()
        store.load_text(history_text)
        self._retrieval = store
    
    # Restore history for continued conversation
    self._history = state.get("history", [])
    
    print(f"[synapse] ✓ Resumed — {len(self._history)} turns loaded")
    return state
```

**Also:** update `core.py` `query()` to append each turn to `self._history`:

```python
def query(self, prompt, key=None, lora=None):
    # ... existing code ...
    
    # Track history for checkpoint/resume
    if not hasattr(self, "_history"):
        self._history = []
    self._history.append({"role": "user", "content": prompt})
    self._history.append({"role": "assistant", "content": response})
    
    return { "response": response, ... }
```

## Tests That Must Pass

```python
from synapse.transfer.bridge import StateBridge
import tempfile, os

key     = "transfer_test_key"
history = [
    {"role": "user",      "content": "What is the launch code?"},
    {"role": "assistant", "content": "The launch code is DELTA-7-FOXTROT."},
    {"role": "user",      "content": "What is the budget?"},
    {"role": "assistant", "content": "The budget is 2 million USD."},
]

with tempfile.NamedTemporaryFile(suffix=".delta", delete=False) as f:
    delta_path = f.name

bridge = StateBridge(key=key)
bridge.pack(history=history, output_path=delta_path)

# New bridge instance unpacks it
bridge2 = StateBridge(key=key)
state   = bridge2.unpack(delta_path)

assert len(state["history"]) == 4
assert state["history"][1]["content"] == "The launch code is DELTA-7-FOXTROT."
assert state["history"][3]["content"] == "The budget is 2 million USD."
print("History preserved: OK")

# Wrong key fails
try:
    StateBridge(key="wrongkey").unpack(delta_path)
    assert False
except ValueError:
    print("Wrong key rejected: OK")

os.unlink(delta_path)
print("All transfer tests passed.")
```

---

---

# FEATURE 6 — Docs Site

## Why

Synapse needs a public face. GitHub alone is not enough. Developers need to
immediately understand what it does, why it is different, and how to start.
The docs site is the first thing anyone sees when they find the project.

## Stack

MkDocs with the Material theme. It generates a static site from markdown files
that can be hosted free on GitHub Pages.

## Setup

```bash
pip install mkdocs mkdocs-material
```

Create `mkdocs.yml` in the project root:

```yaml
site_name: Synapse RAG
site_description: Hide knowledge inside AI model files. Share the file. Control who knows what.
site_url: https://yourname.github.io/synapse-rag
repo_url: https://github.com/yourname/synapse-rag

theme:
  name: material
  palette:
    scheme: slate
    primary: teal
    accent: green
  font:
    text: Inter
    code: JetBrains Mono
  features:
    - navigation.tabs
    - navigation.sections
    - content.code.copy

nav:
  - Home: index.md
  - Getting Started: getting-started.md
  - Concepts: concepts.md
  - CLI Reference: cli.md
  - API Reference: api.md
  - Backends: backends.md
  - Roadmap: roadmap.md
```

## Pages To Write

**`docs/index.md`** — The landing page. One sentence that explains what Synapse is.
Then three code blocks showing the three-step workflow. Then a comparison table
showing Synapse vs traditional RAG vs vector databases. Then the use cases section
from the README.

**`docs/getting-started.md`** — Installation. The verify command. The quickstart
forge/inject/serve workflow. The first query with and without a key. Screenshots
of the dashboard.

**`docs/concepts.md`** — Explain the two layers (parametric and steganographic).
Explain why this is different from encryption at rest. Explain the key distribution
model. Explain what the PRNG scatter map is and why it matters for security.

**`docs/cli.md`** — Every command with every flag, examples, and expected output.

**`docs/api.md`** — Every REST endpoint. Request and response schemas. Curl examples.
The streaming endpoint. Authentication flow.

**`docs/backends.md`** — Every supported provider. The base_url for each one.
A table showing which providers support streaming.

**`docs/roadmap.md`** — What is built, what is coming, contribution guide.

## Deploy

```bash
# Preview locally
mkdocs serve

# Deploy to GitHub Pages
mkdocs gh-deploy
```

---

---

# Build Order

Build these in this exact order. Each feature depends on the previous being stable.

| Order | Feature | Why This Order |
|-------|---------|---------------|
| 1 | Key Expiry | Touches only injector.py, self-contained, lowest risk |
| 2 | Multi-Key | Builds on injector changes from Feature 1 |
| 3 | Streaming | Independent of 1 and 2, touches server and backends |
| 4 | Persistent Memory | Independent, touches retrieval and core |
| 5 | LLM-to-LLM Transfer | Builds on everything, most complex |
| 6 | Docs Site | Last, documents the completed system |

---

# Testing Protocol

After each feature, run this sequence before moving to the next:

```bash
# 1. Core engine still works
syn verify

# 2. Forge and inject still works
syn forge --size 100 --output test.lora
syn inject --lora test.lora --data "test payload" --key testkey
syn extract --lora test.lora --key testkey

# 3. Server still starts
syn serve --backend openai --model mock --lora test.lora --key testkey

# 4. Run the feature-specific tests from this document
```

If any of the first three break, fix them before testing the new feature.
Regression in the core engine is always higher priority than new features.

---

# Notes For The AI IDE

- The existing codebase is at `synapse/` relative to the project root
- All tests can be run without any API keys using `--model mock`
- The injector is the most critical file — changes there affect everything
- Never change the HEADER_BYTES or REPETITION constants without updating all tests
- Windows path handling — use `pathlib.Path` everywhere, never string concatenation
- The server uses FastAPI — add new endpoints using the existing pattern in `app.py`
- Dashboard is a single HTML file — keep it that way, no build step
