export class SynapseEngine {
  private worker: Worker | null = null;

  constructor(private passkey: string) {}

  private initWorker() {
    if (!this.worker) {
      this.worker = new Worker(new URL('../workers/synapse.worker.ts', import.meta.url));
    }
    return this.worker;
  }

  public async forge(
    payload: string | Uint8Array, 
    maskName: string, 
    originalFilename?: string,
    density: number = 1.0,
    onProgress?: (progress: number, status: string) => void
  ): Promise<{ filename: string, buffer: Blob }> { // Return Blob instead of ArrayBuffer
    const worker = this.initWorker();
    
    return new Promise((resolve, reject) => {
      worker.onmessage = (e) => {
        const { type, value, status, result, error } = e.data;
        
        if (type === 'PROGRESS' && onProgress) {
          onProgress(value, status);
        } else if (type === 'FORGE_COMPLETE') {
          // result contains { filename, parts: ArrayBuffer[] }
          // We construct the Blob here on the main thread
          const blob = new Blob(result.parts, { type: 'application/octet-stream' });
          resolve({ filename: result.filename, buffer: blob });
          worker.terminate();
          this.worker = null;
        } else if (type === 'ERROR') {
          reject(new Error(error));
          worker.terminate();
          this.worker = null;
        }
      };
      
      worker.onerror = (err) => {
        reject(err);
        worker.terminate();
        this.worker = null;
      };

<<<<<<< HEAD
      worker.postMessage({
        type: 'FORGE',
        passkey: this.passkey,
        payload,
        maskName,
        originalFilename,
        density
      });
=======
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

  public async forge(payload: string | Uint8Array, maskName: string): Promise<{ filename: string, buffer: ArrayBuffer }> {
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
>>>>>>> 4b1925c (feat: Add Models and Security tabs to Web Portal. Fix binary handling and binary-text detection in Bridge.)
    });
  }

  public async unmask(
    buffer: ArrayBuffer,
    onProgress?: (progress: number, status: string) => void
  ): Promise<{ data: Uint8Array, filename: string }> {
    const worker = this.initWorker();
    
    return new Promise((resolve, reject) => {
      worker.onmessage = (e) => {
        const { type, value, status, result, error } = e.data;
        
        if (type === 'PROGRESS' && onProgress) {
          onProgress(value, status);
        } else if (type === 'UNMASK_COMPLETE') {
          resolve(result);
          worker.terminate();
          this.worker = null;
        } else if (type === 'ERROR') {
          reject(new Error(error));
          worker.terminate();
          this.worker = null;
        }
      };
      
      worker.onerror = (err) => {
        reject(err);
        worker.terminate();
        this.worker = null;
      };

      // We transfer the buffer to the worker to save memory
      worker.postMessage({
        type: 'UNMASK',
        passkey: this.passkey,
        buffer
      }, [buffer]);
    });
  }

  public async unmask(buffer: ArrayBuffer): Promise<{ payload: string, metadata: any }> {
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
    const indices = this.getIndices(weightShape, numBits);
    
    const PRECISION = 1000000;
    const bits: number[] = [];
    
    for (let i = 0; i < numBits; i++) {
      const idx = indices[i];
      const scaled = Math.round(weights[idx] * PRECISION);
      bits.push(scaled & 1);
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
    
    return {
      payload: payload,
      text: new TextDecoder().decode(payload),
      metadata: meta
    };
  }
}
