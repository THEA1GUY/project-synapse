import mammoth from 'mammoth';
import * as XLSX from 'xlsx';
import * as pdfjs from 'pdfjs-dist';

// Configure PDF worker for browser environments
if (typeof window !== 'undefined' && !pdfjs.GlobalWorkerOptions.workerSrc) {
  pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;
}

export async function extractText(data: Uint8Array, filename: string): Promise<string> {
  const ext = filename.split('.').pop()?.toLowerCase();
  
  if (!ext) return '';

  try {
    // DOCX
    if (ext === 'docx') {
      let options: any = {};
      if (typeof window === 'undefined') {
        // Node environment: use buffer
        options.buffer = Buffer.from(data);
      } else {
        // Browser environment: use arrayBuffer
        options.arrayBuffer = data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength);
      }
      const result = await mammoth.extractRawText(options);
      return result.value;
    }
    
    // EXCEL
    if (ext === 'xlsx' || ext === 'xls') {
      const workbook = XLSX.read(data, { type: 'array' });
      let text = '';
      workbook.SheetNames.forEach(sheetName => {
        const sheet = workbook.Sheets[sheetName];
        // sheet_to_txt creates tab-separated text
        const sheetText = XLSX.utils.sheet_to_txt(sheet);
        if (sheetText.trim()) {
           text += sheetText + '\n';
        }
      });
      return text;
    }
    
    // PDF
    if (ext === 'pdf') {
      // In Node.js, we might need to set up a standard font or worker
      // For now, we use standard getDocument
      const loadingTask = pdfjs.getDocument({ data });
      const doc = await loadingTask.promise;
      
      let fullText = '';
      for (let i = 1; i <= doc.numPages; i++) {
        const page = await doc.getPage(i);
        const textContent = await page.getTextContent();
        const pageText = textContent.items
          // @ts-ignore - item has str property in standard flow
          .map((item: any) => item.str)
          .join(' ');
        fullText += pageText + '\n';
      }
      return fullText;
    }

    return '';

  } catch (error) {
    console.error(`UnifiedParser: Error parsing file ${filename}`, error);
    return ''; // Graceful failure
  }
}
