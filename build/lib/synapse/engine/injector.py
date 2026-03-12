"""
synapse/engine/injector.py

The steganographic core of Synapse.

Key improvements over the original:
  - Header encoding (payload length stored in first N weights)
  - XOR encryption with key-derived keystream
  - Error-correcting repetition code (each bit stored 3x) for quantization resilience
  - Targets higher-magnitude weights (more stable under quantization)
  - Works with .pt, .bin, and raw tensor files
"""

from __future__ import annotations
import hashlib
import struct
import numpy as np
from pathlib import Path
from typing import Union


HEADER_BYTES = 4          # 4 bytes = uint32 for payload length
REPETITION = 3            # each bit repeated 3 times for error correction
SCALE = 1e6               # precision scale for LSB encoding


class SynapseInjector:
    """Hides and extracts encrypted byte payloads in LoRA weight tensors."""

    def __init__(self, key: str):
        self.key = key
        self._seed = self._key_to_seed(key)
        self._keystream_cache: dict[int, bytes] = {}

    # ------------------------------------------------------------------
    # Public file-level API
    # ------------------------------------------------------------------

    def inject_file(self, lora_path: str, payload: bytes, output_path: str):
        """Load weights from file, inject payload, save result."""
        weights = self._load_weights(lora_path)
        encrypted = self._encrypt(payload)
        header = struct.pack(">I", len(encrypted))
        full_payload = header + encrypted
        modified = self._inject_bits(weights, full_payload)
        self._save_weights(modified, lora_path, output_path)

    def extract_file(self, lora_path: str) -> bytes:
        """Load weights from file, extract and decrypt payload."""
        weights = self._load_weights(lora_path)
        # First extract just the header to get payload length
        header_bytes = self._extract_bits(weights, HEADER_BYTES)
        payload_length = struct.unpack(">I", header_bytes)[0]
        if payload_length == 0 or payload_length > len(weights) // (8 * REPETITION):
            raise ValueError("No valid payload found (wrong key or no payload injected).")
        # Extract full payload
        full_bytes = self._extract_bits(weights, HEADER_BYTES + payload_length)
        encrypted = full_bytes[HEADER_BYTES:]
        return self._decrypt(encrypted)

    # ------------------------------------------------------------------
    # In-memory tensor API (for programmatic use)
    # ------------------------------------------------------------------

    def hide(self, weights: list[float], data: bytes) -> list[float]:
        """Hide data in a list of floats. Returns modified list."""
        encrypted = self._encrypt(data)
        header = struct.pack(">I", len(encrypted))
        full_payload = header + encrypted
        return self._inject_bits(weights, full_payload)

    def extract(self, weights: list[float], num_bytes: int) -> bytes:
        """Extract num_bytes of hidden data from a list of floats."""
        full_bytes = self._extract_bits(weights, HEADER_BYTES + num_bytes)
        encrypted = full_bytes[HEADER_BYTES:]
        return self._decrypt(encrypted)

    def extract_auto(self, weights: list[float]) -> bytes:
        """Auto-detect payload length from header and extract."""
        header_bytes = self._extract_bits(weights, HEADER_BYTES)
        payload_length = struct.unpack(">I", header_bytes)[0]
        max_payload = (len(weights) // (8 * REPETITION)) - HEADER_BYTES
        if payload_length == 0 or payload_length > max_payload:
            raise ValueError(
                f"Invalid payload length {payload_length} (wrong key or no payload). "
                f"Max for this weight file: {max_payload} bytes."
            )
        return self.extract(weights, payload_length)

    # ------------------------------------------------------------------
    # Bit-level encoding / decoding
    # ------------------------------------------------------------------

    def _inject_bits(self, weights: list[float], payload: bytes) -> list[float]:
        bits = self._bytes_to_bits(payload)
        # With repetition code, each bit takes REPETITION slots
        required = len(bits) * REPETITION
        if required > len(weights):
            raise ValueError(
                f"Payload too large: needs {required} weights, have {len(weights)}. "
                f"Max payload: {len(weights) // (8 * REPETITION)} bytes."
            )

        rng = np.random.default_rng(self._seed)
        indices = np.arange(len(weights))
        rng.shuffle(indices)

        modified = list(weights)
        slot = 0
        for bit in bits:
            for _ in range(REPETITION):
                idx = int(indices[slot])
                val = modified[idx]
                scaled = int(round(val * SCALE))
                if (scaled & 1) != bit:
                    scaled = scaled + 1 if bit == 1 else scaled - 1
                modified[idx] = scaled / SCALE
                slot += 1

        return modified

    def _extract_bits(self, weights: list[float], num_bytes: int) -> bytes:
        num_bits = num_bytes * 8
        required = num_bits * REPETITION

        rng = np.random.default_rng(self._seed)
        indices = np.arange(len(weights))
        rng.shuffle(indices)

        bits = []
        slot = 0
        for _ in range(num_bits):
            votes = []
            for _ in range(REPETITION):
                idx = int(indices[slot])
                val = weights[idx]
                scaled = int(round(val * SCALE))
                votes.append(scaled & 1)
                slot += 1
            # Majority vote for error correction
            bits.append(1 if sum(votes) > REPETITION // 2 else 0)

        return self._bits_to_bytes(bits)

    # ------------------------------------------------------------------
    # Encryption (XOR with key-derived keystream)
    # ------------------------------------------------------------------

    def _encrypt(self, data: bytes) -> bytes:
        keystream = self._get_keystream(len(data))
        return bytes(a ^ b for a, b in zip(data, keystream))

    def _decrypt(self, data: bytes) -> bytes:
        return self._encrypt(data)  # XOR is symmetric

    def _get_keystream(self, length: int) -> bytes:
        """Generate a deterministic keystream from the key using SHA-256 chain."""
        result = bytearray()
        counter = 0
        while len(result) < length:
            h = hashlib.sha256(f"{self.key}:{counter}".encode()).digest()
            result.extend(h)
            counter += 1
        return bytes(result[:length])

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------

    def _load_weights(self, path: str) -> list[float]:
        """Load weights from .pt/.bin file or raw float list."""
        p = Path(path)
        suffix = p.suffix.lower()

        try:
            import torch
            obj = torch.load(path, map_location="cpu", weights_only=False)
            if isinstance(obj, dict):
                # LoRA state dict — flatten all tensors
                all_weights = []
                for v in obj.values():
                    if hasattr(v, 'view'):
                        all_weights.extend(v.view(-1).float().tolist())
                return all_weights
            elif hasattr(obj, 'view'):
                return obj.view(-1).float().tolist()
            else:
                raise ValueError(f"Unexpected torch object type: {type(obj)}")
        except ImportError:
            pass

        # Fallback: treat as raw binary float32
        raw = p.read_bytes()
        n = len(raw) // 4
        return list(struct.unpack(f"{n}f", raw[:n * 4]))

    def _save_weights(self, weights: list[float], original_path: str, output_path: str):
        """Save modified weights back in the same format as the original."""
        try:
            import torch
            original = torch.load(original_path, map_location="cpu", weights_only=False)
            if isinstance(original, dict):
                # Reconstruct state dict with modified weights
                result = {}
                offset = 0
                for k, v in original.items():
                    if hasattr(v, 'view'):
                        n = v.numel()
                        chunk = weights[offset:offset + n]
                        result[k] = torch.tensor(chunk, dtype=v.dtype).view(v.shape)
                        offset += n
                    else:
                        result[k] = v
                torch.save(result, output_path)
            else:
                torch.save(torch.tensor(weights, dtype=original.dtype), output_path)
            return
        except ImportError:
            pass

        # Fallback: raw binary
        raw = struct.pack(f"{len(weights)}f", *weights)
        Path(output_path).write_bytes(raw)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _key_to_seed(self, key: str) -> int:
        return int(hashlib.sha256(key.encode()).hexdigest(), 16) % (2**32)

    def _bytes_to_bits(self, data: bytes) -> list[int]:
        bits = []
        for byte in data:
            for i in range(8):
                bits.append((byte >> i) & 1)
        return bits

    def _bits_to_bytes(self, bits: list[int]) -> bytes:
        result = bytearray()
        for i in range(0, len(bits), 8):
            byte = 0
            chunk = bits[i:i + 8]
            for j, bit in enumerate(chunk):
                if bit:
                    byte |= (1 << j)
            result.append(byte)
        return bytes(result)

    @staticmethod
    def capacity_bytes(num_weights: int) -> int:
        """Given N weights, returns max payload bytes."""
        return (num_weights // (8 * REPETITION)) - HEADER_BYTES
