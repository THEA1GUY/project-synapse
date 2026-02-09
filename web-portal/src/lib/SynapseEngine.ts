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

      worker.postMessage({
        type: 'FORGE',
        passkey: this.passkey,
        payload,
        maskName,
        originalFilename,
        density
      });
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
}
