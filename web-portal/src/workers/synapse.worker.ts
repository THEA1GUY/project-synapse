// synapse.worker.ts
// Handles intensive computations for SynapseEngine (forge/unmask) off-thread.
// Uses BitSet Linear Scan optimization for O(N) streaming processing with low memory.

/* eslint-disable no-restricted-globals */

interface WorkerMessage {
  type: 'FORGE' | 'UNMASK';
  payload?: any;
  passkey?: string;
  maskName?: string;
  originalFilename?: string;
  buffer?: ArrayBuffer;
  density?: number; // 1.0 (Standard), 0.5 (Sparse), 2.0 (Dense)
}

let randomSeed = 0;

// Initialize the worker with a passkey hash
async function init(passkey: string) {
  const msgUint8 = new TextEncoder().encode(passkey);
  const hashBuffer = await crypto.subtle.digest('SHA-256', msgUint8);
  const hashArray = new Uint32Array(hashBuffer);
  randomSeed = hashArray[0];
}

// Deterministic PRNG
function nextRandom(seed: number): number {
  return (seed * 1664525 + 1013904223) % 4294967296;
}

// Generate a BitSet where the k-th set bit represents the k-th payload bit's position
// Returns the BitSet and the total number of weights used
function generateCarrierMap(numBits: number, densityMultiplier: number): { bitSet: Uint8Array, numWeights: number } {
  // Density: 1.0 -> 10x weights. 0.5 -> 20x weights (High Stealth). 2.0 -> 5x weights (High Capacity).
  // Base multiplier is 10.
  // effectiveMultiplier = 10 / density. 
  // e.g. density 1.0 -> 10x. density 2.0 -> 5x. density 0.5 -> 20x.
  const effectiveMultiplier = Math.max(10 / (densityMultiplier || 1.0), 2);
  const numWeights = Math.floor(Math.max(numBits * effectiveMultiplier, 10000));
  
  const bitSetSize = Math.ceil(numWeights / 8);
  const bitSet = new Uint8Array(bitSetSize);

  let seed = randomSeed;
  let count = 0;

  // We need exactly numBits carriers.
  // We use the collision method to pick them randomly.
  while (count < numBits) {
    seed = nextRandom(seed);
    const candidate = seed % numWeights;
    
    const byteIdx = Math.floor(candidate / 8);
    const bitIdx = candidate % 8;
    const mask = 1 << bitIdx;

    if ((bitSet[byteIdx] & mask) === 0) {
      bitSet[byteIdx] |= mask;
      count++;
    }
  }

  return { bitSet, numWeights };
}

function crc32(data: Uint8Array): number {
  let crc = 0xffffffff;
  const table = new Uint32Array(256);
  for (let i = 0; i < 256; i++) {
    let c = i;
    for (let j = 0; j < 8; j++) {
      c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
    }
    table[i] = c;
  }
  for (let i = 0; i < data.length; i++) {
    crc = (crc >>> 8) ^ table[(crc ^ data[i]) & 0xff];
  }
  return (crc ^ 0xffffffff) >>> 0;
}

async function forge(payload: string | Uint8Array, maskName: string, originalFilename: string, density: number) {
  const rawData = typeof payload === 'string' ? new TextEncoder().encode(payload) : payload;
  const checksum = crc32(rawData);
  
  const protectedPayload = new Uint8Array(rawData.length + 4);
  protectedPayload.set(rawData);
  new DataView(protectedPayload.buffer).setUint32(rawData.length, checksum, true);

  const numBits = protectedPayload.length * 8;
  
  postMessage({ type: 'PROGRESS', value: 10, status: 'Mapping Neural Space...' });
  
  // 1. Generate Map
  const { bitSet, numWeights } = generateCarrierMap(numBits, density);
  
  // 2. Stream Generation
  const CHUNK_SIZE = 1024 * 1024; // 1M weights per chunk (4MB)
  const chunks: ArrayBuffer[] = [];
  const PRECISION = 1000000;
  
  let seed = randomSeed + 1;
  let bitCursor = 0; // Which bit of payload are we embedding?

  postMessage({ type: 'PROGRESS', value: 20, status: 'Forging Neural Weights...' });

  for (let offset = 0; offset < numWeights; offset += CHUNK_SIZE) {
    const end = Math.min(offset + CHUNK_SIZE, numWeights);
    const size = end - offset;
    const chunkWeights = new Float32Array(size);
    
    // Generate Base Weights
    for (let i = 0; i < size; i++) {
      seed = nextRandom(seed);
      chunkWeights[i] = (seed / 4294967296) * 0.1 - 0.05;
    }

    // Apply Embedding
    for (let i = 0; i < size; i++) {
      const globalIdx = offset + i;
      const byteIdx = Math.floor(globalIdx / 8);
      const mask = 1 << (globalIdx % 8);
      
      if (bitSet[byteIdx] & mask) {
        // This weight carries the next payload bit
        if (bitCursor < numBits) {
           const payloadByte = Math.floor(bitCursor / 8);
           const payloadBit = bitCursor % 8;
           const bit = (protectedPayload[payloadByte] >> payloadBit) & 1;
           
           let scaled = Math.round(chunkWeights[i] * PRECISION);
           if ((scaled & 1) !== bit) {
             scaled += bit === 1 ? 1 : -1;
           }
           chunkWeights[i] = scaled / PRECISION;
           
           bitCursor++;
        }
      }
    }
    
    // Copy to ArrayBuffer to transfer
    // We can't transfer Float32Array buffer directly if it's a slice of a larger one, 
    // but here we created a new one for the chunk.
    chunks.push(chunkWeights.buffer);

    // Progress
    if (offset % (CHUNK_SIZE * 5) === 0) {
      const p = 20 + Math.floor((offset / numWeights) * 60);
      postMessage({ type: 'PROGRESS', value: p, status: 'Encoding Layers...' });
    }
  }

  // Header
  const weightDataLen = numWeights * 4;
  const header = JSON.stringify({
    "__metadata__": {
      "type": "synapse_v1_hardened",
      "payload_bytes": rawData.length.toString(),
      "total_bytes": protectedPayload.length.toString(),
      "filename": originalFilename || (typeof payload === 'string' ? "knowledge.txt" : "payload.bin"),
      "density": density
    },
    "stealth_weights": {
      "dtype": "F32",
      "shape": [numWeights],
      "data_offsets": [0, weightDataLen]
    }
  });
  
  const headerBuf = new TextEncoder().encode(header);
  const padding = (8 - (headerBuf.length % 8)) % 8;
  const paddedHeader = new Uint8Array(headerBuf.length + padding);
  paddedHeader.set(headerBuf);
  for (let i = 0; i < padding; i++) paddedHeader[headerBuf.length + i] = 32;

  // We return the components to be assembled into a Blob on the main thread
  // header, chunks
  
  // Wait, we need to return one structure.
  // Can we construct the final buffer?
  // If weights are 3.3GB, we CANNOT construct one buffer.
  // We must return the chunks.
  
  return {
    filename: `synapse_${maskName.toLowerCase().replace(/\s+/g, '_')}.safetensors`,
    header: paddedHeader.buffer,
    chunks: chunks
  };
}

async function unmask(buffer: ArrayBuffer) {
  const view = new DataView(buffer);
  const headerLen = Number(view.getBigUint64(0, true));
  const headerStr = new TextDecoder().decode(new Uint8Array(buffer, 8, headerLen));
  const header = JSON.parse(headerStr);
  
  const origSize = parseInt(header.__metadata__.payload_bytes);
  const totalSize = parseInt(header.__metadata__.total_bytes);
  const filename = header.__metadata__.filename || "restored_payload.bin";
  const numWeights = header.stealth_weights.shape[0];
  const density = header.__metadata__.density || 1.0;
  
  const numBits = totalSize * 8;

  postMessage({ type: 'PROGRESS', value: 10, status: 'Mapping Neural Space...' });
  const { bitSet } = generateCarrierMap(numBits, density);

  const result = new Uint8Array(totalSize);
  let bitCursor = 0;
  const PRECISION = 1000000;

  postMessage({ type: 'PROGRESS', value: 30, status: 'Extracting Knowledge...' });

  const weightsOffset = 8 + headerLen;
  const weightsEnd = buffer.byteLength;
  
  // We can read directly from the buffer without copying to Float32Array if we are careful,
  // but Float32Array constructor on a buffer is fast (view).
  // However, accessing a 3.3GB buffer might be an issue? No, buffer exists.
  // Wait, if the input `buffer` is > 2GB, some browsers might have issues with single ArrayBuffer?
  // But usually 64-bit systems allow it.
  
  // To be safe and efficient, let's iterate.
  // The weights are at weightsOffset.
  const weights = new Float32Array(buffer, weightsOffset, numWeights);
  
  for (let i = 0; i < numWeights; i++) {
    const byteIdx = Math.floor(i / 8);
    const mask = 1 << (i % 8);
    
    if (bitSet[byteIdx] & mask) {
      if (bitCursor < numBits) {
        const scaled = Math.round(weights[i] * PRECISION);
        const bit = scaled & 1;
        
        if (bit) {
          const payloadByte = Math.floor(bitCursor / 8);
          const payloadBit = bitCursor % 8;
          result[payloadByte] |= (1 << payloadBit);
        }
        
        bitCursor++;
      }
    }
    
    if (i % 1000000 === 0) {
       const progress = 30 + Math.floor((i / numWeights) * 60);
       postMessage({ type: 'PROGRESS', value: progress, status: 'Extracting Knowledge...' });
    }
  }

  const checksum = new DataView(result.buffer).getUint32(origSize, true);
  const payload = result.slice(0, origSize);
  
  if (crc32(payload) !== checksum) {
    throw new Error("Integrity check failed: Checksum mismatch.");
  }

  return { data: payload, filename };
}

self.onmessage = async (e: MessageEvent<WorkerMessage>) => {
  const { type, passkey, payload, maskName, originalFilename, buffer, density } = e.data;

  try {
    if (type === 'FORGE') {
      if (passkey) await init(passkey);
      const { filename, header, chunks } = await forge(payload, maskName!, originalFilename!, density || 1.0);
      
      // Combine header length (8 bytes) + header + chunks
      // We return the parts so main thread can blob them
      const lenBuf = new ArrayBuffer(8);
      new DataView(lenBuf).setBigUint64(0, BigInt(header.byteLength), true);
      
      const parts = [lenBuf, header, ...chunks];
      const transferables = parts.filter(p => p instanceof ArrayBuffer);
      
      postMessage({ type: 'FORGE_COMPLETE', result: { filename, parts } }, transferables as any);
      
    } else if (type === 'UNMASK') {
      if (passkey) await init(passkey);
      const result = await unmask(buffer!);
      postMessage({ type: 'UNMASK_COMPLETE', result }, [result.data.buffer]);
    }
  } catch (error: any) {
    postMessage({ type: 'ERROR', error: error.message });
  }
};
