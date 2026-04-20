"""
prospectus_loader.py

Extract text from a PDF and split into hierarchical (section-based) chunks.
"""

import pandas as pd
import re
from pypdf import PdfReader

class ProspectusLoader:
    def __init__(self, chunk_size=1500, chunk_overlap=50):
        """
        chunk_size and chunk_overlap are kept for compatibility,
        but hierarchical splitting ignores them - we split by headings.
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def extract_text(self, pdf_path):
        """Extract all text from a PDF file."""
        reader = PdfReader(pdf_path)
        text = ""
        for page_num, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text()
            if page_text:
                text += f"\n\n[Page {page_num}]\n" + page_text
        print(f"OK: Extracted {len(text)} characters from {pdf_path}")
        return text

    def _is_heading(self, line: str) -> bool:
        """
        Heuristic to detect heading lines.
        Returns True if the line looks like a section heading.
        """
        line = line.strip()
        if not line:
            return False
        # Heading candidates: all caps, ends with colon, starts with number + dot, short length
        if line.isupper() and len(line) < 80:
            return True
        if line.endswith(':') and len(line) < 80:
            return True
        if re.match(r'^\d+(\.\d+)*\s+', line):  # e.g., "1. Introduction"
            return True
        if re.match(r'^[A-Z][a-z]+\s+[A-Z][a-z]+', line) and len(line) < 60:
            # Likely a title case heading
            return True
        return False

    def chunk_text_hierarchical(self, text: str):
        """
        Split text into chunks based on headings.
        Each chunk starts at a heading and continues until the next heading (or end).
        """
        lines = text.split('\n')
        chunks = []
        current_chunk_lines = []
        in_heading = False

        for line in lines:
            if self._is_heading(line):
                # If we were already building a chunk, save it
                if current_chunk_lines:
                    chunk_text = '\n'.join(current_chunk_lines).strip()
                    if chunk_text:
                        chunks.append(chunk_text)
                    current_chunk_lines = []
                # Start new chunk with this heading
                current_chunk_lines.append(line)
                in_heading = True
            else:
                current_chunk_lines.append(line)
                in_heading = False

        # Append the last chunk
        if current_chunk_lines:
            chunk_text = '\n'.join(current_chunk_lines).strip()
            if chunk_text:
                chunks.append(chunk_text)

        print(f"OK: Hierarchical splitting created {len(chunks)} chunks")
        return chunks

    def chunk_text(self, text):
        """
        Public method - uses hierarchical splitting by default.
        """
        return self.chunk_text_hierarchical(text)

    def load_and_chunk(self, pdf_path):
        """Extract text, split hierarchically, return DataFrame."""
        text = self.extract_text(pdf_path)
        chunks = self.chunk_text(text)
        df = pd.DataFrame({
            "text": chunks,
            "metadata": [
                {"source": "prospectus", "chunk_id": i, "text_preview": chunks[i][:100]}
                for i in range(len(chunks))
            ]
        })
        # Add placeholder columns for compatibility with VectorStore
        df["Question"] = "Prospectus excerpt"
        df["Answer"] = df["text"]
        df["Department"] = "General"
        df["Tags"] = ""
        df["ID"] = [f"PROS_{i}" for i in range(len(chunks))]
        return df