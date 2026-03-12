# Synapse RAG — Complete Usage Guide

---

## What is Synapse?

Synapse is a Python library that lets you hide knowledge inside AI model files (LoRAs). The model looks and behaves completely normally to anyone who uses it. But if you have the right secret key, the model suddenly has access to hidden knowledge and answers from it.

Think of it like invisible ink. The letter still looks like a normal letter. Only you can see what's actually written in it.

---

## Installation

```bash
# Clone or download the synapse folder into your project
# Then install from the folder that contains setup.py

pip install -e .
```

**Install extras based on what you need:**

```bash
pip install openai          # for OpenAI, Groq, Together, OpenRouter, Ollama
pip install anthropic       # for Anthropic Claude

pip install torch transformers peft trl datasets   # for training LoRAs
pip install unsloth                                 # makes training 2-5x faster

pip install sentence-transformers   # makes retrieval smarter (optional)
```

---

## The Three Steps

Every Synapse workflow follows the same three steps:

```
1. TRAIN   → teach a LoRA your knowledge base
2. INJECT  → hide sensitive/dynamic data in the LoRA steganographically  
3. SERVE   → run the API + dashboard
```

You can skip step 1 if you already have a LoRA or just want to test with random weights.

---

## Step 1 — Train a LoRA on your documents

This bakes your entire knowledge base into the LoRA. The model genuinely learns the content — no retrieval needed for this layer.

**Via Python:**

```python
from synapse import Synapse

app = Synapse(backend="openai", model="gpt-4o", api_key="sk-...")

app.train(
    data_path="./my_docs/",   # folder of .txt .md .pdf .docx .html .json files
    output_path="./my.lora",
    mode="fast",              # "tiny" (<1min) | "fast" (2-5min) | "quality" (15-30min)
)
```

**Via CLI:**

```bash
synapse train \
  --data ./my_docs/ \
  --output my.lora \
  --mode fast
```

**Modes explained:**

| Mode    | Model          | RAM     | Time on CPU  | Use when                        |
|---------|---------------|---------|-------------|----------------------------------|
| tiny    | TinyLlama 1.1B | 2-3 GB  | < 1 min     | Quick testing                    |
| fast    | Phi-3-mini     | 4-6 GB  | 2-5 min     | Most use cases (default)         |
| quality | Llama-3-8B     | 8-12 GB | 15-30 min   | Best knowledge retention         |

**Supported file types:**

`.txt` `.md` `.rst` `.html` `.json` `.csv` `.pdf` (needs `pip install pypdf`) `.docx` (needs `pip install python-docx`)

---

## Step 2 — Inject the stego layer

This hides additional data (sensitive, dynamic, or frequently updated content) inside the LoRA using steganography. This layer is only accessible with the secret key.

**Via Python:**

```python
app.inject(
    data="./secrets.md",     # file path OR a raw string
    key="my_secret_password",
    lora="./my.lora",        # not needed if you just called app.train()
)
```

**Via CLI:**

```bash
synapse inject \
  --lora my.lora \
  --data ./secrets.md \
  --key my_secret_password
```

**What can you hide:**
- Sensitive facts that shouldn't be visible if someone opens the file
- Dynamic context that changes frequently (re-inject without retraining)
- System prompt configuration
- Access credentials or API references
- User-specific or deployment-specific information

**Capacity:**
A 50K weight LoRA holds roughly 2,000 bytes of stego payload. A trained LoRA from `synapse train` holds more depending on rank and mode. The CLI will tell you the exact capacity when you run `synapse forge`.

---

## Step 3 — Serve the API and dashboard

**Via Python:**

```python
app.serve(port=8000)
```

**Via CLI:**

```bash
synapse serve \
  --backend openai \
  --model gpt-4o \
  --api-key sk-... \
  --lora my.lora \
  --key my_secret_password   # auto-unlocks on startup
```

Once running:
- Dashboard → `http://localhost:8000`
- API docs  → `http://localhost:8000/docs`

---

## Using the API

### Query without a key (normal chatbot behavior)

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What are the access codes?"}'
```

Response:
```json
{
  "response": "I don't have information about access codes.",
  "context_used": false,
  "unlocked": false,
  "chunks_retrieved": 0
}
```

### Query with a key (hidden knowledge unlocked)

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What are the access codes?", "key": "my_secret_password"}'
```

Response:
```json
{
  "response": "The primary access code is ALPHA-7, secondary is BRAVO-9.",
  "context_used": true,
  "unlocked": true,
  "chunks_retrieved": 2
}
```

### Pre-unlock (load context once, don't send key every request)

```bash
curl -X POST http://localhost:8000/unlock \
  -H "Content-Type: application/json" \
  -d '{"key": "my_secret_password"}'
```

After this, all subsequent `/query` requests automatically use the hidden context without needing the key each time.

### Check server status

```bash
curl http://localhost:8000/status
```

```json
{
  "backend": "openai",
  "model": "gpt-4o",
  "unlocked": true,
  "chunk_count": 14,
  "lora_loaded": "./my.lora"
}
```

---

## Supported Backends

All providers except Anthropic use the same `backend="openai"` setting. You just change the `model`, `api_key`, and `base_url`.

```python
# OpenAI
Synapse(backend="openai", model="gpt-4o", api_key="sk-...")

# Gemini
Synapse(backend="openai", model="gemini-1.5-pro",
        api_key="your-google-key",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/")

# Groq (fast, free tier available)
Synapse(backend="openai", model="llama3-8b-8192",
        api_key="gsk-...",
        base_url="https://api.groq.com/openai/v1")

# OpenRouter (access hundreds of models with one key)
Synapse(backend="openai", model="mistralai/mixtral-8x7b",
        api_key="sk-or-...",
        base_url="https://openrouter.ai/api/v1")

# Ollama (local, completely free, no API key)
Synapse(backend="openai", model="llama3",
        base_url="http://localhost:11434/v1")

# GLM
Synapse(backend="openai", model="glm-4",
        api_key="...",
        base_url="https://open.bigmodel.cn/api/paas/v4")

# Together AI
Synapse(backend="openai", model="meta-llama/Llama-3-8b-chat-hf",
        api_key="...",
        base_url="https://api.together.xyz/v1")

# Anthropic Claude (only one that needs its own backend name)
Synapse(backend="anthropic", model="claude-sonnet-4-6", api_key="sk-ant-...")
```

---

## CLI Reference

### `synapse verify`
Test that the core engine works correctly. Run this first after installing.
```bash
synapse verify
```

### `synapse forge`
Create a blank carrier LoRA for testing (random weights, no training needed).
```bash
synapse forge --size 100 --output carrier.lora
# size is in thousands of weights
# 100 = 100,000 weights = ~4,000 bytes of stego capacity
```

### `synapse train`
Train a LoRA on your documents.
```bash
synapse train \
  --data ./docs/ \
  --output trained.lora \
  --mode fast \
  --epochs 1 \
  --reserve 8192
```

### `synapse inject`
Hide data inside a LoRA.
```bash
synapse inject \
  --lora trained.lora \
  --data ./sensitive.md \
  --key mypassword \
  --output trained_with_payload.lora   # optional, defaults to overwriting
```

### `synapse extract`
Pull the hidden data back out.
```bash
synapse extract \
  --lora trained_with_payload.lora \
  --key mypassword \
  --output recovered.md   # optional, prints to terminal if omitted
```

### `synapse serve`
Start the API server and dashboard.
```bash
synapse serve \
  --backend openai \
  --model gpt-4o \
  --api-key sk-... \
  --lora trained_with_payload.lora \
  --key mypassword \
  --port 8000
```

---

## Full Python Workflow Example

```python
from synapse import Synapse

# 1. Initialize with your backend
app = Synapse(
    backend="openai",
    model="gpt-4o-mini",
    api_key="sk-..."
)

# 2. Train on your knowledge base
app.train(
    data_path="./company_docs/",
    output_path="./company.lora",
    mode="fast",
)

# 3. Hide sensitive data in the stego layer
app.inject(
    data="./internal_only.md",
    key="company_secret_2025",
)

# 4. Test a query programmatically
result = app.query(
    prompt="What is the Q2 budget?",
    key="company_secret_2025",
)
print(result["response"])
print("Context used:", result["context_used"])

# 5. Start the server
app.serve(port=8000)
```

---

## Testing Without Training (Quick Start)

If you just want to test the system works before training anything:

```bash
# 1. Create a blank carrier LoRA
synapse forge --size 100 --output test.lora

# 2. Hide some text in it
synapse inject --lora test.lora --data "The secret is: the answer is 42." --key testkey

# 3. Verify it comes back out
synapse extract --lora test.lora --key testkey

# 4. Start the server with mock backend (no API key needed)
synapse serve --backend openai --model mock --lora test.lora --key testkey
```

Or in Python:

```python
from synapse import Synapse

app = Synapse(backend="openai", model="mock", base_url="http://localhost:11434/v1")
# Using Ollama with a mock — swap for real backend when ready
```

---

## Common Issues

**`synapse: command not found`**
Run `pip install -e .` from the folder containing `setup.py`.

**`No valid payload found (wrong key or nothing injected)`**
The key you used to extract doesn't match the key used to inject. Keys are case-sensitive.

**`Payload too large`**
Your hidden data is bigger than the LoRA's stego capacity. Either use a larger LoRA (`synapse forge --size 500`) or compress/shorten your payload.

**`Cannot reach Ollama`**
Start Ollama first with `ollama serve`, then make sure your model is downloaded: `ollama pull llama3`.

**Out of memory during training**
Switch to a smaller mode: `--mode tiny`. Or reduce sequence length: `--seq-len 256`.

---

## What Gets Stored Where

| Layer | What's in it | Who can access it |
|-------|-------------|-------------------|
| Parametric (trained) | Your entire knowledge base | Anyone using the model |
| Steganographic (injected) | Sensitive / dynamic data | Only with the secret key |

The parametric layer is always active. The stego layer only activates with the right key. Same model file, two layers of knowledge.
