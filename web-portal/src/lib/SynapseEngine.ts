export class SynapseEngine {
  private randomSeed: number = 0;

  constructor(private passkey: string) {}

  private async init() {
    const msgUint8 = new TextEncoder().encode(this.passkey);
    const hashBuffer = await crypto.subtle.digest('SHA-256', msgUint8);
    const hashArray = new Uint32Array(hashBuffer);
    this.randomSeed = hashArray[0];
  }

  private getIndices(totalElements: number, numBits: number, onProgress?: (p: number) => void): number[] {
    const indices = Array.from({ length: totalElements }, (_, i) => i);
    let seed = this.randomSeed;
    
    for (let i = indices.length - 1; i > 0; i--) {
      seed = (seed * 1664525 + 1013904223) % 4294967296;
      const j = seed % (i + 1);
      [indices[i], indices[j]] = [indices[j], indices[i]];
      
      if (onProgress && i % 10000 === 0) {
        onProgress(Math.round(((totalElements - i) / totalElements) * 100));
      }
    }
    
    return indices.slice(0, numBits);
  }

  private crc32(data: Uint8Array): number {
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

  public async forge(
    payload: string | Uint8Array, 
    maskName: string, 
    originalFilename?: string, 
    onProgress?: (p: number, status: string) => void
  ): Promise<{ filename: string, buffer: ArrayBuffer }> {
    if (onProgress) onProgress(5, 'Initializing Neural Core...');
    await this.init();
    
    const rawData = typeof payload === 'string' ? new TextEncoder().encode(payload) : payload;
    const checksum = this.crc32(rawData);
    
    const protectedPayload = new Uint8Array(rawData.length + 4);
    protectedPayload.set(rawData);
    new DataView(protectedPayload.buffer).setUint32(rawData.length, checksum, true);

    const bits: number[] = [];
    protectedPayload.forEach(byte => {
      for (let i = 0; i < 8; i++) {
        bits.push((byte >> i) & 1);
      }
    });

    const numWeights = Math.max(bits.length * 10, 10000);
    const weights = new Float32Array(numWeights);
    
    if (onProgress) onProgress(15, 'Generating Neural Forest...');
    let seed = this.randomSeed + 1;
    for (let i = 0; i < numWeights; i++) {
      seed = (seed * 1664525 + 1013904223) % 4294967296;
      weights[i] = (seed / 4294967296) * 0.1 - 0.05;
    }

    if (onProgress) onProgress(30, 'Mapping Synaptic Indices...');
    const indices = this.getIndices(numWeights, bits.length, (p) => {
      if (onProgress) onProgress(30 + (p * 0.3), 'Mapping Synaptic Indices...');
    });
    
    const PRECISION = 1000000;

    if (onProgress) onProgress(60, 'Injecting Knowledge Bits...');
    for (let i = 0; i < bits.length; i++) {
      const idx = indices[i];
      let scaled = Math.round(weights[idx] * PRECISION);
      if ((scaled & 1) !== bits[i]) {
        scaled += bits[i] === 1 ? 1 : -1;
      }
      weights[idx] = scaled / PRECISION;
      
      if (onProgress && i % 5000 === 0) {
        onProgress(60 + (i / bits.length) * 30, 'Injecting Knowledge Bits...');
      }
    }

    if (onProgress) onProgress(90, 'Finalizing Safetensors...');
    const weightData = new Uint8Array(weights.buffer);
    const header = JSON.stringify({
      "__metadata__": {
        "type": "synapse_v1_hardened",
        "payload_bytes": rawData.length.toString(),
        "total_bytes": protectedPayload.length.toString(),
        "original_filename": originalFilename || "secret.txt"
      },
      "stealth_weights": {
        "dtype": "F32",
        "shape": [numWeights],
        "data_offsets": [0, weightData.length]
      }
    });
    
    const headerBuf = new TextEncoder().encode(header);
    const padding = (8 - (headerBuf.length % 8)) % 8;
    const paddedHeader = new Uint8Array(headerBuf.length + padding);
    paddedHeader.set(headerBuf);
    for (let i = 0; i < padding; i++) paddedHeader[headerBuf.length + i] = 32;

    const totalSize = 8 + paddedHeader.length + weightData.length;
    const finalBuffer = new ArrayBuffer(totalSize);
    const view = new DataView(finalBuffer);
    
    view.setBigUint64(0, BigInt(paddedHeader.length), true);
    new Uint8Array(finalBuffer, 8, paddedHeader.length).set(paddedHeader);
    new Uint8Array(finalBuffer, 8 + paddedHeader.length).set(weightData);

    if (onProgress) onProgress(100, 'Forge Complete.');
    return {
      filename: `synapse_${maskName.toLowerCase().replace(/\s+/g, '_')}.safetensors`,
      buffer: finalBuffer
    };
  }

  public async unmask(
    buffer: ArrayBuffer,
    onProgress?: (p: number, status: string) => void
  ): Promise<{ payload: Uint8Array, text: string, metadata: any }> {
    if (onProgress) onProgress(10, 'Initializing extraction...');
    await this.init();
    
    const view = new DataView(buffer);
    const headerSize = Number(view.getBigUint64(0, true));
    
    const headerBuf = new Uint8Array(buffer, 8, headerSize);
    const header = JSON.parse(new TextDecoder().decode(headerBuf));
    
    const meta = header["__metadata__"];
    const payloadBytes = parseInt(meta.payload_bytes);
    const totalBytes = parseInt(meta.total_bytes);
    
    const weightShape = header["stealth_weights"]["shape"][0];
    const weightData = new Uint8Array(buffer, 8 + headerSize);
    const weights = new Float32Array(weightData.buffer, weightData.byteOffset, weightShape);

    const numBits = totalBytes * 8;
    
    if (onProgress) onProgress(30, 'Reconstructing indices...');
    const indices = this.getIndices(weightShape, numBits, (p) => {
      if (onProgress) onProgress(30 + (p * 0.3), 'Reconstructing indices...');
    });
    
    const PRECISION = 1000000;
    const bits: number[] = [];
    
    if (onProgress) onProgress(60, 'Extracting neural bits...');
    for (let i = 0; i < numBits; i++) {
      const idx = indices[i];
      const scaled = Math.round(weights[idx] * PRECISION);
      bits.push(scaled & 1);
      if (onProgress && i % 5000 === 0) {
        onProgress(60 + (i / numBits) * 30, 'Extracting neural bits...');
      }
    }
    
    const decodedPayload = new Uint8Array(totalBytes);
    for (let i = 0; i < totalBytes; i++) {
      let byte = 0;
      for (let j = 0; j < 8; j++) {
        if (bits[i * 8 + j]) byte |= (1 << j);
      }
      decodedPayload[i] = byte;
    }
    
    const payload = decodedPayload.slice(0, payloadBytes);
    const checksum = new DataView(decodedPayload.buffer, decodedPayload.byteOffset).getUint32(payloadBytes, true);
    
    if (this.crc32(payload) !== checksum) {
      throw new Error("Integrity failure: Checksum mismatch or invalid passkey.");
    }
    
    if (onProgress) onProgress(100, 'Extraction complete.');
    return {
      payload: payload,
      text: new TextDecoder().decode(payload),
      metadata: meta
    };
  }
}
