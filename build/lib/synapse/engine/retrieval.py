"""
synapse/engine/retrieval.py

Lightweight in-memory retrieval store for RAG.
No external vector DB required — pure Python.
"""

from __future__ import annotations
import re
from typing import Optional

class RetrievalStore:
    """
    Chunk text, index it, and retrieve relevant chunks for a query.
    Supports smart CSV detection with header persistence.
    """

    def __init__(self, chunk_size: int = 400, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.chunks: list[str] = []
        self.header = ""
        self.is_csv = False
        self._embeddings = None
        self._use_embeddings = False

    def load(self, text: str):
        """Build searchable index from extracted secret text."""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        
        # Smart CSV Detection
        if len(lines) > 2 and "," in lines[0] and "," in lines[1]:
            # CSV Path: Keep header for every row
            self.header = lines[0]
            self.chunks = lines[1:]
            self.is_csv = True
        else:
            # Standard Text Path: Split into overlapping context chunks
            self.header = ""
            self.is_csv = False
            self.chunks = self._chunk_text(text)
            
        self._try_build_embeddings()

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)

    def retrieve(self, query: str, top_k: int = 3) -> list[str]:
        """Return the top_k most relevant chunks for a query."""
        if not self.chunks:
            return []

        # FULL LEDGER MODE: If it's a CSV and it's small (under 50 rows),
        # just give the AI the whole table so it can reason perfectly.
        if self.is_csv and len(self.chunks) < 50:
            all_rows = "\n".join(self.chunks)
            return [f"Context (Full Knowledge Base Table):\nHeaders: {self.header}\n{all_rows}"]

        # Standard RAG Path for large documents or massive CSVs
        effective_k = 10 if self.is_csv else top_k

        if self._use_embeddings and self._embeddings is not None:
            raw_results = self._retrieve_embeddings(query, effective_k)
        else:
            raw_results = self._retrieve_tfidf(query, effective_k)

        # Post-process: Add CSV headers if needed
        results = []
        for res in raw_results:
            if self.is_csv and self.header:
                results.append(f"Context (Table Row):\nHeaders: {self.header}\nData: {res}")
            else:
                results.append(res)
        return results

    # ------------------------------------------------------------------
    # Internal Logic
    # ------------------------------------------------------------------

    def _chunk_text(self, text: str) -> list[str]:
        """Split text into overlapping chunks, respecting sentence boundaries."""
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        chunks = []
        current = []
        current_len = 0

        for sentence in sentences:
            sentence_len = len(sentence)
            if current_len + sentence_len > self.chunk_size and current:
                chunks.append(" ".join(current))
                current = current[-1:] # Keep small overlap
                current.append(sentence)
                current_len = sum(len(s) for s in current)
            else:
                current.append(sentence)
                current_len += sentence_len

        if current:
            chunks.append(" ".join(current))
        return [c for c in chunks if c.strip()]

    def _retrieve_tfidf(self, query: str, top_k: int) -> list[str]:
        """Simple keyword matching fallback."""
        query_words = set(re.findall(r'\w+', query.lower()))
        scores = []
        for chunk in self.chunks:
            chunk_lower = chunk.lower()
            score = sum(1 for word in query_words if word in chunk_lower)
            scores.append(score)

        indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [self.chunks[i] for i in indices if scores[i] > 0]

    def _try_build_embeddings(self):
        """Upgrade to semantic search if possible."""
        try:
            from sentence_transformers import SentenceTransformer
            import numpy as np
            model = SentenceTransformer("all-MiniLM-L6-v2")
            self._embeddings = model.encode(self.chunks, normalize_embeddings=True)
            self._embed_model = model
            self._use_embeddings = True
        except ImportError:
            self._use_embeddings = False

    def _retrieve_embeddings(self, query: str, top_k: int) -> list[str]:
        import numpy as np
        q_emb = self._embed_model.encode([query], normalize_embeddings=True)
        scores = (self._embeddings @ q_emb.T).flatten()
        ranked = np.argsort(scores)[::-1][:top_k]
        return [self.chunks[i] for i in ranked if scores[i] > 0.1]
