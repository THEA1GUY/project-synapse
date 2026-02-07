# Project Synapse: Neural Steganography for Decentralized RAG

## Abstract
Project Synapse introduces **Synaptic RAG**, a novel architecture for infrastructure-free, secure knowledge distribution. By utilizing high-dimensional weight-space steganography, Synapse enables the injection of encrypted data payloads into functional neural network adapters (LoRAs). This approach allows for the decentralized broadcast of private context via public model channels, requiring only a cryptographic seed for just-in-time extraction and retrieval augmentation.

## Usage: The Hardened Forge
Project Synapse provides a simple, zero-dependency TUI for forging neural masks and bridging them to local LLMs (Ollama).

### 1. Forge a Neural Mask
Hide your secret data inside a functional weight adapter.
```bash
python3 synapse_tui.py
```
*   **Input:** Your secret text payload.
*   **Mask Name:** The public-facing name of the adapter.
*   **Passkey:** The cryptographic seed (min 8 characters).
*   **Result:** A `.safetensors` file containing the hidden context and a CRC32 integrity check.

### 2. Bridge to Ollama (Ghost RAG)
Unmask the context and talk to it using a local LLM.
```bash
python3 synapse_ollama.py
```
*   **Authentication:** Provide the path to the `.safetensors` file and your passkey.
*   **Verification:** The system verifies the CRC32 checksum locally.
*   **Injection:** The unmasked data is injected into Ollama as a transient system prompt for zero-footprint RAG.

## Repository Structure
- `src/synapse/core`: The mathematical engine for bit-level weight manipulation and dynamic model mapping.
- `src/synapse/api`: High-performance FastAPI implementation for JIT RAG operations.
- `src/synapse/cli`: The primary user interface for injection and extraction protocols.
- `docs/WHITE_PAPER.md`: Detailed theoretical foundation and technical specifications.
- `docs/TECHNICAL_GUIDE.md`: Conceptual overview and non-technical explanation of the underlying logic.
- `experiments/`: Validation protocols and bit-integrity verification scripts.

## Core Methodology
The system utilizes a "Trojan Horse" strategy where a mundane carrier model (the mask) provides public utility while concealing a sparse, high-entropy payload within the least significant bits (LSB) of non-critical weights. The mapping of these bits is determined by a deterministic PRNG sequence initialized by the user's private key.

## Usage
Refer to `docs/WHITE_PAPER.md` for implementation details and command references.

---
*A research project exploring the boundaries of neural data persistence.*
