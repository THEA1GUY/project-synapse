# 📟 Project Synapse: Neural Steganography Forge

> **V6.0 [BANKER-GRADE]: Infrastructure-free, decentralized knowledge distribution through functional weight-space steganography.**

---

## 🚀 Version 6.0: The Production Milestone
Project Synapse has evolved from a research prototype to a hardened, high-performance production engine. V6.0 introduces multi-threaded processing and a massive reduction in memory overhead, enabling the distribution of large-scale knowledge bases hidden inside functional model weights.

### 💎 V6.0 Highlights:
*   **WebWorker Core:** Off-thread computations for zero-latency UI.
*   **BitSet Scan:** 30x reduction in memory footprint for large files.
*   **Production Bridge:** Seamless integration between Web Dashboard and Local Python TUI.
*   **Precision Hardening:** 100% bit-accurate restoration across CPU/GPU environments.

---

## 🌟 The "Secret Radio" Concept
Imagine a vast library where every book appears normal to the public. However, by using a **Secret Key**, you can see microscopic variations in the ink of specific letters across thousands of pages. When these variations are reconstructed, they reveal a completely different, hidden book.

In Synapse, the "library" is a LoRA adapter. The "ink" is the neural weights. The "hidden book" is your private context.

---

## 🛠 How It Works (The Architecture)

### 1. The Forge (Injection)
The system uses **LSB (Least Significant Bit) Steganography** applied to `float32` tensors.
*   **Bit-Mapping:** A SHA-256 hash of your **Passkey** initializes a deterministic PRNG sequence. This sequence selects sparse indices across the model's weight layers using a memory-optimized **BitSet Linear Scan**.
*   **Neural Shifting:** The payload is bit-packed and injected into the 6th decimal place of the selected weights. This shift is mathematically calculated to be below the threshold of model degradation (<0.01%), ensuring the carrier model remains functional.
*   **Integrity Guard:** Every payload includes a **CRC32 Checksum** to prevent data corruption during extraction.

### 2. The Ghost Driver (Extraction)
The extraction process is **just-in-time** and stateless.
*   **Zero-Footprint:** The secret context is reconstructed directly into RAM. It never touches the disk in unmasked form.
*   **Stereoscopic Unmasking:** By providing the Passkey, the system reconstructs the PRNG map and pulls the original bits from the weight tensors.

### 3. Ghost RAG (Ollama Integration)
Once the context is unmasked, it is injected into a local LLM as a **Transient System Prompt**. To the outside observer, you are simply chatting with a standard model. Internally, the model is being driven by the "Ghost" data unlocked from the LoRA.

---

## 🚀 Plug-and-Play Workflow

### Step 1: Forge a Neural Mask
Hide your secret text inside a functional weight adapter.
```bash
python3 synapse_tui.py
```
1.  Enter your secret payload (text or file path).
2.  Define the public "Mask Name".
3.  **Authentication Choice:** 
    *   **A. Manual Passkey:** Pick your own password.
    *   **B. Neural Access Token:** Generates a high-entropy seed and a signed `SYN-` token.

### Step 2: Bridge to Ollama
Talk to your secret knowledge using a local LLM.
```bash
python3 synapse_ollama.py
```
1.  Path to your generated `.safetensors` file.
2.  **Passkey or SYN- Token:** The system automatically detects and verifies tokens.
3.  Your query.

---

## 🌐 Synapse Founder Portal (Web UI)
The production-ready web dashboard for managing neural steganography at scale.
- **Location:** `synapse-portal/`
- **Stack:** Next.js 15, TypeScript, Vanilla CSS (Material 3).
- **Features:** 
    - **Worker-Driven:** Multi-threaded computation for large files.
    - **Blob-Assembly:** Efficient file regeneration for downloads.
    - **Neural Vault:** Persistent storage of your forged masks and tokens.

---

## 🛡 Security & Hardening
*   **Skeptical Verification:** The bridge verifies the embedded CRC32 checksum before unmasking. If the key is off by even one character, the integrity check fails, preventing leakage of gibberish.
*   **Precision Buffer:** Synapse V6.0 uses a 6-decimal scaling factor to ensure stability across different CPU/GPU rounding architectures.
*   **Compatibility:** Generated files follow the official `safetensors` binary format, making them indistinguishable from standard model weights to most scanners.

---

## 🗺 Use Cases
*   **Sovereign Knowledge Base:** Carry your entire personal Wiki hidden inside a common LoRA.
*   **Corporate Privacy:** Distribute sensitive company data to employees via public model channels without exposing the raw data to the cloud.
*   **Off-Grid RAG:** Perform high-fidelity retrieval-augmented generation in environments with zero internet and high surveillance.

---

## 📂 Repository Structure
- `synapse_tui.py`: The Hardened Forge (CLI Interface).
- `synapse_ollama.py`: The Ghost RAG Bridge (Ollama Integration).
- `src/synapse/core`: The mathematical engine for weight manipulation.
- `experiments/`: Bit-integrity verification and stress-test protocols.

---
*Developed by SenatraxAI. Exploring the boundaries of neural data persistence.* 🦾📟
