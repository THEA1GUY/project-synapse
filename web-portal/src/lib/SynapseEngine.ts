export class SynapseEngine {
  private randomSeed: number = 0;

  constructor(private passkey: string) {}

  private async init() {
    const msgUint8 = new TextEncoder().encode(this.passkey);
    const hashBuffer = await crypto.subtle.digest('SHA-256', msgUint8);
    const hashArray = new Uint32Array(hashBuffer);
    this.randomSeed = hashArray[0];
  }

  private getIndices(totalElements: number, numBits: number): number[] {
    const indices = Array.from({ length: totalElements }, (_, i) => i);
    let seed = this.randomSeed;
    
    for (let i = indices.length - 1; i > 0; i--) {
      seed = (seed * 1664525 + 1013904223) % 4294967296;
      const j = seed % (i + 1);
      [indices[i], indices[j]] = [indices[j], indices[i]];
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

  public async forge(payload: string | Uint8Array, maskName: string, originalFilename?: string): Promise<{ filename: string, buffer: ArrayBuffer }> {
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
    
    let seed = this.randomSeed + 1;
    for (let i = 0; i < numWeights; i++) {
      seed = (seed * 1664525 + 1013904223) % 4294967296;
      weights[i] = (seed / 4294967296) * 0.1 - 0.05;
    }

    const indices = this.getIndices(numWeights, bits.length);
    const PRECISION = 1000000;

    for (let i = 0; i < bits.length; i++) {
      const idx = indices[i];
      let scaled = Math.round(weights[idx] * PRECISION);
      if ((scaled & 1) !== bits[i]) {
        scaled += bits[i] === 1 ? 1 : -1;
      }
      weights[idx] = scaled / PRECISION;
    }

    const weightData = new Uint8Array(weights.buffer);
    const header = JSON.stringify({
      "__metadata__": {
        "type": "synapse_v1_hardened",
        "payload_bytes": rawData.length.toString(),
        "total_bytes": protectedPayload.length.toString(),
        "filename": originalFilename || (typeof payload === 'string' ? "knowledge.txt" : "payload.bin")
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

    return {
      filename: `synapse_${maskName.toLowerCase().replace(/\s+/g, '_')}.safetensors`,
      buffer: finalBuffer
    };
  }

  public async unmask(buffer: ArrayBuffer): Promise<{ data: Uint8Array, filename: string }> {
    await this.init();
    const view = new DataView(buffer);
    const headerLen = Number(view.getBigUint64(0, true));
    const headerStr = new TextDecoder().decode(new Uint8Array(buffer, 8, headerLen));
    const header = JSON.parse(headerStr);
    
    const origSize = parseInt(header.__metadata__.payload_bytes);
    const totalSize = parseInt(header.__metadata__.total_bytes);
    const filename = header.__metadata__.filename || "restored_payload.bin";
    const numWeights = header.stealth_weights.shape[0];
    
    const weightBuf = new Uint8Array(buffer, 8 + headerLen);
    const weights = new Float32Array(weightBuf.buffer, weightBuf.byteOffset, numWeights);
    
    const bits: number[] = [];
    const numBits = totalSize * 8;
    const indices = this.getIndices(numWeights, numBits);
    const PRECISION = 1000000;

    for (let i = 0; i < numBits; i++) {
      const idx = indices[i];
      const scaled = Math.round(weights[idx] * PRECISION);
      bits.push(scaled & 1);
    }

    const result = new Uint8Array(totalSize);
    for (let i = 0; i < totalSize; i++) {
      let byte = 0;
      for (let j = 0; j < 8; j++) {
        if (bits[i * 8 + j]) byte |= (1 << j);
      }
      result[i] = byte;
    }

    const checksum = new DataView(result.buffer).getUint32(origSize, true);
    const payload = result.slice(0, origSize);
    if (this.crc32(payload) !== checksum) {
      throw new Error("Integrity check failed: Checksum mismatch.");
    }

    return { data: payload, filename };
  }
}
