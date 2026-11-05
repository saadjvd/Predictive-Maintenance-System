from typing import List, Dict, Any
import re


class DocumentChunker:
    """Chunks technical pharmaceutical SOPs and equipment manuals into semantic segments."""

    DEFAULT_CHUNK_SIZE = 400  # Words
    DEFAULT_CHUNK_OVERLAP = 50  # Words

    @classmethod
    def chunk_text(
        cls,
        text: str,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_CHUNK_OVERLAP,
        chunk_overlap: int = None,
        metadata: Dict[str, Any] = None,
    ) -> List[Dict[str, Any]]:
        """
        Chunks plain text into overlapping word windows while preserving section headers.
        """
        if chunk_overlap is not None:
            overlap = chunk_overlap
        metadata = metadata or {}
        # Clean text
        clean_text = re.sub(r"\s+", " ", text).strip()
        words = clean_text.split()

        if not words:
            return []

        chunks: List[Dict[str, Any]] = []
        start = 0
        chunk_idx = 0

        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk_words = words[start:end]
            chunk_content = " ".join(chunk_words)

            # Detect section header in chunk if present
            section_match = re.search(r"(?:Section|Chapter|Step|SOP|Procedure)\s+[\d\.]+", chunk_content, re.IGNORECASE)
            section = section_match.group(0) if section_match else metadata.get("section", "General")

            chunks.append({
                "chunk_index": chunk_idx,
                "content": chunk_content,
                "metadata": {
                    **metadata,
                    "section": section,
                    "word_count": len(chunk_words),
                },
            })

            chunk_idx += 1
            if end >= len(words):
                break
            start += max(chunk_size - overlap, 1)

        return chunks

    split_text = chunk_text
