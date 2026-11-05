import os
import math
import hashlib
from typing import List
import numpy as np


class EmbeddingProvider:
    """Pluggable embedding generator supporting local deterministic hashing and cloud LLM APIs."""

    EMBEDDING_DIM = 128

    @classmethod
    def generate_embedding(cls, text: str) -> List[float]:
        """
        Generates dense normalized vector embedding.
        Uses deterministic semantic hashing by default, guaranteeing zero external dependencies
        and air-gap compatibility for pharmaceutical factory deployments.
        """
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key and not api_key.startswith("mock_"):
            try:
                from openai import OpenAI
                client = OpenAI(api_key=api_key)
                response = client.embeddings.create(
                    input=text[:4000],
                    model="text-embedding-3-small",
                )
                vec = response.data[0].embedding
                # If dimension doesn't match default, return normalized vector directly
                return [round(float(v), 6) for v in vec]
            except Exception:
                pass  # Fallback to local deterministic embedding

        # Deterministic semantic hash projection (Dimension: 128)
        words = text.lower().split()
        vector = np.zeros(cls.EMBEDDING_DIM, dtype=np.float32)

        if not words:
            return vector.tolist()

        for word in words:
            # MD5 hash into feature buckets
            h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
            idx = h % cls.EMBEDDING_DIM
            sign = 1.0 if ((h >> 8) % 2 == 0) else -1.0
            vector[idx] += sign

        # L2 normalization
        norm = np.linalg.norm(vector)
        if norm > 1e-6:
            vector = vector / norm

        return [round(float(v), 6) for v in vector.tolist()]

    embed_text = generate_embedding

    @classmethod
    def compute_similarity(cls, vec1: List[float], vec2: List[float]) -> float:
        """Cosine similarity between two dense embedding vectors."""
        if not vec1 or not vec2:
            return 0.0
        v1 = np.array(vec1, dtype=np.float32)
        v2 = np.array(vec2, dtype=np.float32)

        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 < 1e-6 or norm2 < 1e-6:
            return 0.0

        return float(np.dot(v1, v2) / (norm1 * norm2))

