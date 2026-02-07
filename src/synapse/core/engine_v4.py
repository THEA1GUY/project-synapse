import hashlib
import random
import zlib
import struct
import json
import os
import numpy as np

class SynapseV4Engine:
    """
    Synapse V4: Spectral Hardening Engine.
    Uses Walsh-Hadamard Transforms (WHT) to spread data across neural blocks.
    """
    def __init__(self, passkey: str):
        self.passkey = passkey
        self.seed = int.from_bytes(hashlib.sha256(passkey.encode()).digest()[:4], 'little')
        self.block_size = 8 # Power of 2 for WHT

    def _fwht(self, a):
        """Fast Walsh-Hadamard Transform."""
        n = len(a)
        if n == 1:
            return a
        a_left = self._fwht(a[0:n//2])
        a_right = self._fwht(a[n//2:n])
        res = np.zeros(n)
        res[0:n//2] = a_left + a_right
        res[n//2:n] = a_left - a_right
        return res

    def forge_spectral(self, payload_data, mask_name):
        """Hides data in the frequency domain of neural blocks."""
        if isinstance(payload_data, str):
            raw_data = payload_data.encode('utf-8')
        else:
            raw_data = payload_data
            
        checksum = zlib.crc32(raw_data) & 0xffffffff
        protected_payload = raw_data + struct.pack('<I', checksum)
        
        bits = []
        for byte in protected_payload:
            for i in range(8):
                bits.append((byte >> i) & 1)
        
        # We spread 1 bit over 1 block (8 weights)
        num_blocks = len(bits)
        num_weights = num_blocks * self.block_size
        
        random.seed(self.seed)
        weights = np.random.uniform(-0.05, 0.05, num_weights)
        
        # Spectral Spreading
        for b in range(num_blocks):
            block = weights[b*self.block_size : (b+1)*self.block_size]
            # Transform to frequency domain
            coeffs = self._fwht(block)
            
            # Target the DC component (first coefficient) for maximum robustness
            # Adjust the parity of the frequency coefficient
            target_val = int(coeffs[0] * 1000) # Scale for stability
            if (target_val & 1) != bits[b]:
                target_val += 1 if bits[b] == 1 else -1
            
            coeffs[0] = target_val / 1000
            
            # Inverse Transform (FWHT is its own inverse, just scale)
            weights[b*self.block_size : (b+1)*self.block_size] = self._fwht(coeffs) / self.block_size
            
        return weights, len(raw_data), len(protected_payload)

    def unmask_spectral(self, weights, orig_size, total_size):
        """Extracts data from the frequency domain."""
        num_blocks = total_size * 8
        bits = []
        
        for b in range(num_blocks):
            block = weights[b*self.block_size : (b+1)*self.block_size]
            coeffs = self._fwht(block)
            
            # Read parity of the DC frequency coefficient
            target_val = int(round(coeffs[0] * 1000))
            bits.append(target_val & 1)
            
        buffer = bytearray()
        for i in range(0, len(bits), 8):
            byte = 0
            for j in range(8):
                if bits[i+j]: byte |= (1 << j)
            buffer.append(byte)
            
        return buffer[:orig_size]
