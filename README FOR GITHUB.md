# Synapse RAG

**Hide knowledge inside AI model files. Share the file. Control who knows what.**

---

Most knowledge bases require a database, a server, cloud credentials, and an auth system. Synapse requires a file and a key.

You inject your documents into a LoRA model file. The knowledge is encrypted inside the weights. Send the file to anyone. Without the key it's a normal model that knows nothing. With the key it answers every question from your hidden knowledge base.

```
Same file. Same model. Completely different reality depending on who holds the key.
```

---

## How It Works

Synapse has two layers:

**Parametric layer** — your entire knowledge base trained directly into the LoRA weights via continued pre-training. The model genuinely knows the content. No retrieval needed.

**Steganographic layer** — sensitive or dynamic content hidden in the least significant bits of the weight values using XOR encryption and PRNG scatter. Invisible without the key. Looks like floating point noise to anyone inspecting the file.

Neither layer is visible without the correct key. Wrong key produces garbage. No key produces a normal chatbot that knows nothing.

---

## Install

```bash
pip install synapse-rag
```

```bash
# Verify everything works
syn verify
```

---

## Quickstart

```bash
# 1. Create a carrier LoRA
syn forge --size 200 --output knowledge.lora

# 2. Hide your documents inside it
syn inject --lora knowledge.lora --data ./your_docs/ --key your_secret_key

# 3. Start the API server
syn serve --backend openai --model gpt-4o --api-key sk-... \
          --lora knowledge.lora --key your_secret_key
```

Open `http://localhost:8000` — your encrypted knowledge base is live.

---

## The Distribution Model

This is what makes Synapse different from every other RAG system.

**Without Synapse:**
- Set up a database
- Configure cloud storage
- Build an auth system
- Manage credentials
- Give collaborators server access

**With Synapse:**
- Send a file
- Share a key separately

The `.lora` file can be emailed, put on GitHub, shared publicly — it's useless without the key. The knowledge is encrypted inside. Your collaborator deploys it in one command with their own API key, on their own machine, with no access to your infrastructure.

```python
# Your friend receives the file and runs this
from synapse import Synapse

app = Synapse(backend="openai", model="gpt-4o", api_key="their-own-key")
app.serve(lora="knowledge.lora", key="key_you_shared_separately")
```

---

## Use Cases

**Portable Company Knowledge Base**
Inject your internal docs — HR policies, product specs, runbooks — into a LoRA. Employees query it with the company key. Contractors get a separate LoRA with only what they need for the job.

**SDK Documentation That Lives Locally**
Ship a LoRA with your developer SDK. The LoRA knows everything about your API. Developers query it locally — no rate limits, no internet required, no API calls to your servers.

**Encrypted Document Sharing**
Share sensitive research or data with collaborators without exposing it publicly. The data lives in the LoRA. Only people with the key can access it. Revoke access by rotating the key.

**Tiered Access API**
One endpoint. No key returns a general assistant. Right key returns a specialist with full domain knowledge. Different keys for different access levels once multi-key is enabled.

**Agency Client Handoff**
Build a client's knowledge base, inject it, hand them the file and the key. They deploy it themselves in one command. You never manage their server.

---

## Supported Backends

Synapse works with any OpenAI-compatible API and Anthropic. You are never locked into a provider.

```python
# OpenAI
Synapse(backend="openai", model="gpt-4o", api_key="sk-...")

# Gemini
Synapse(backend="openai", model="gemini-1.5-pro",
        api_key="your-google-key",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/")

# Groq (fast, free tier)
Synapse(backend="openai", model="llama3-8b-8192",
        api_key="gsk-...",
        base_url="https://api.groq.com/openai/v1")

# OpenRouter (hundreds of models, one key)
Synapse(backend="openai", model="mistralai/mixtral-8x7b",
        api_key="sk-or-...",
        base_url="https://openrouter.ai/api/v1")

# Ollama (local, completely free, no API key)
Synapse(backend="openai", model="llama3",
        base_url="http://localhost:11434/v1")

# Anthropic Claude
Synapse(backend="anthropic", model="claude-sonnet-4-6", api_key="sk-ant-...")
```

Any new provider that launches with an OpenAI-compatible endpoint works immediately. No code changes needed.

---

## Training Your Own LoRA

For larger knowledge bases, train a LoRA directly on your documents. The model genuinely learns the content — no retrieval, no chunking at query time.

```bash
syn train --data ./company_docs/ --output trained.lora --mode fast
```

| Mode    | Model      | RAM    | Time      |
|---------|------------|--------|-----------|
| tiny    | TinyLlama  | 2-3GB  | < 1 min   |
| fast    | Phi-3-mini | 4-6GB  | 2-5 min   |
| quality | Llama-3-8B | 8-12GB | 15-30 min |

After training, inject the stego layer on top:

```bash
syn inject --lora trained.lora --data ./sensitive.md --key your_key
```

---

## API

Once the server is running everything is accessible via REST.

**Query without key** — normal assistant, no hidden knowledge
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What are the access codes?"}'
```

**Query with key** — full hidden knowledge unlocked
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What are the access codes?", "key": "your_secret_key"}'
```

**Pre-unlock** — load context once, all subsequent queries use it
```bash
curl -X POST http://localhost:8000/unlock \
  -H "Content-Type: application/json" \
  -d '{"key": "your_secret_key"}'
```

Full API docs at `http://localhost:8000/docs` when the server is running.

---

## CLI Reference

```bash
syn verify                          # test the engine works
syn forge  --size 200 --output carrier.lora
syn train  --data ./docs --output trained.lora --mode fast
syn inject --lora carrier.lora --data ./secrets.md --key mykey
syn extract --lora carrier.lora --key mykey
syn serve  --backend openai --model gpt-4o --api-key sk-... \
           --lora carrier.lora --key mykey --port 8000
```

---

## Security Model

- The `.lora` file is safe to share publicly — it contains no readable data without the key
- XOR encryption with SHA-256 derived keystream makes the payload unreadable
- PRNG scatter pattern (seeded by your key) determines which weights store which bits — unknown without the key
- Wrong key produces a header with a garbage length value, caught and rejected cleanly
- 3x repetition code provides error correction across minor floating point perturbations

The key should always travel separately from the file. Different channels, different times.

---

## Roadmap

- [x] Steganographic injection and extraction
- [x] In-memory RAG with TF-IDF and embedding retrieval
- [x] FastAPI server with live dashboard
- [x] Multi-backend support (OpenAI-compatible + Anthropic)
- [x] Continued pre-training on raw documents
- [ ] Key expiry — time-limited access built into the key itself
- [ ] Multi-key multi-payload — different keys unlock different content from the same file
- [ ] Streaming responses
- [ ] Persistent memory across server restarts
- [ ] LLM-to-LLM context passing via LoRA delta
- [ ] Docs site

---

## License

MIT
