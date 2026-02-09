import numpy as np
import torch
from typing import List, Tuple
import hashlib

class SynapseInjector:
    def __init__(self, seed: str):
        self.seed = seed
        self.rng = np.random.default_rng(self._seed_to_int(seed))

    def _seed_to_int(self, seed: str) -> int:
        return int(hashlib.sha256(seed.encode()).hexdigest(), 16) % (2**32)

    def _get_shuffled_indices(self, total_elements: int, num_bits: int) -> List[int]:
        """
        Memory-efficient BitSet-based collision handling for large models.
        """
        indices = []
        # Use a bytearray as a bitset to save space (1 bit per weight)
        bitset = bytearray((total_elements + 7) // 8)
        
        count = 0
        while count < num_bits:
            idx = self.rng.integers(0, total_elements)
            # Check if bit is set
            if not (bitset[idx >> 3] & (1 << (idx & 7))):
                bitset[idx >> 3] |= (1 << (idx & 7))
                indices.append(int(idx))
                count += 1
        
        # Explicitly clear bitset memory
        del bitset
        return indices

    def hide(self, weights: torch.Tensor, data: bytes) -> torch.Tensor:
        """
        Hides data bits into the LSB of the weights.
        """
        # Convert bytes to bit array
        bits = []
        for byte in data:
            for i in range(8):
                bits.append((byte >> i) & 1)
        
        num_bits = len(bits)
        flat_weights = weights.view(-1).cpu().detach().numpy()
        
        if num_bits > len(flat_weights):
            raise ValueError(f"Data too large: {num_bits} bits > {len(flat_weights)} weights")

        # Get pseudo-random indices to hide bits
        indices = self._get_shuffled_indices(len(flat_weights), num_bits)
        
        # Inject bits using LSB manipulation on the float representation
        # For simplicity in this demo, we'll use a fixed precision trick or 
        # convert to float32 and modify the last bit of the mantissa.
        # Here we use a simpler approach: encode in the parity of a rounded integer.
        
        modified_weights = flat_weights.copy()
        for i, idx in enumerate(indices):
            # Scale weight to make it an integer for bit manipulation
            # This is a naive LSB. In real synapse we might use more subtle methods.
            val = modified_weights[idx]
            # Use a multiplier to reach a precision where LSB is stable
            scaled = int(val * 1e7) 
            # Set LSB to bit
            if (scaled & 1) != bits[i]:
                if bits[i] == 1:
                    scaled += 1
                else:
                    scaled -= 1
            modified_weights[idx] = float(scaled) / 1e7

        return torch.tensor(modified_weights).view(weights.shape)

    def extract(self, weights: torch.Tensor, num_bytes: int) -> bytes:
        """
        Extracts hidden bits from the LSB of the weights.
        """
        num_bits = num_bytes * 8
        flat_weights = weights.view(-1).cpu().detach().numpy()
        indices = self._get_shuffled_indices(len(flat_weights), num_bits)
        
        bits = []
        for idx in indices:
            val = flat_weights[idx]
            scaled = round(val * 1e7)
            bits.append(scaled & 1)
            
        # Convert bits to bytes
        extracted_bytes = bytearray()
        for i in range(0, len(bits), 8):
            byte = 0
            for j in range(8):
                if bits[i + j]:
                    byte |= (1 << j)
            extracted_bytes.append(byte)
            
        return bytes(extracted_bytes)
