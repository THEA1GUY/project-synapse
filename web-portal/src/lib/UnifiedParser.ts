import * as XLSX from 'xlsx';

export async function extractText(data: Uint8Array, filename: string): Promise<string> {
  const ext = filename.split('.').pop()?.toLowerCase();
  
  if (!ext) return '';

  try {
    // DOCX
    if (ext === 'docx') {
      const mammoth = await import('mammoth');
      let options: any = {};
      if (typeof window === 'undefined') {
        options.buffer = Buffer.from(data);
      } else {
        options.arrayBuffer = data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength);
      }
      const result = await mammoth.extractRawText(options);
      return result.value;
    }
    
    // EXCEL / CSV
    if (ext === 'xlsx' || ext === 'xls' || ext === 'csv') {
      const workbook = XLSX.read(data, { type: 'array' });
      let text = '';
      workbook.SheetNames.forEach(sheetName => {
        const sheet = workbook.Sheets[sheetName];
        const sheetText = XLSX.utils.sheet_to_txt(sheet);
        if (sheetText.trim()) {
           text += `--- SHEET: ${sheetName} ---\n${sheetText}\n`;
        }
      });
      return text;
    }
    
    // PDF
    if (ext === 'pdf') {
      const pdfjs = await import('pdfjs-dist');
      if (typeof window !== 'undefined') {
        pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;
      }

      const loadingTask = pdfjs.getDocument({ data });
      const doc = await loadingTask.promise;
      
      let fullText = '';
      for (let i = 1; i <= doc.numPages; i++) {
        const page = await doc.getPage(i);
        const textContent = await page.getTextContent();
        const pageText = textContent.items
          // @ts-ignore
          .map((item: any) => item.str)
          .join(' ');
        fullText += pageText + '\n';
      }
      return fullText;
    }

    // Try plain text decoding for everything else
    try {
      const decoder = new TextDecoder('utf-8', { fatal: true });
      return decoder.decode(data);
    } catch {
      return ''; 
    }

  } catch (error) {
    console.error(`UnifiedParser: Error parsing file ${filename}`, error);
    return ''; 
  }
}
