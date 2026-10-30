from __future__ import annotations

import re
from typing import Sequence

import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from app.config import EMBEDDING_MODEL
from app.ingest import Chunk


def tokenize(text: str) -> list[str]:
    # Keeps useful code identifiers and error codes together.
    return re.findall(r"[A-Za-z0-9_./:-]+", text.lower())


class HybridIndex:
    def __init__(self, embedding_model: str = EMBEDDING_MODEL):
        self.embedding_model_name = embedding_model
        self.model: SentenceTransformer | None = None
        self.chunks: list[Chunk] = []
        self.faiss_index = None
        self.bm25 = None

    def _get_model(self) -> SentenceTransformer:
        if self.model is None:
            self.model = SentenceTransformer(self.embedding_model_name, device="cpu")
        return self.model

    def build(self, chunks: Sequence[Chunk], batch_size: int = 32) -> int:
        self.chunks = list(chunks)

        if not self.chunks:
            self.faiss_index = None
            self.bm25 = None
            return 0

        texts = [c.text for c in self.chunks]
        model = self._get_model()

        import torch
        # Guard against OpenMP threading crashes on macOS
        if torch.get_num_threads() > 1:
            torch.set_num_threads(1)

        embeddings = model.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        embeddings = np.asarray(embeddings, dtype=np.float32)

        self.faiss_index = faiss.IndexFlatIP(embeddings.shape[1])
        self.faiss_index.add(embeddings)

        self.bm25 = BM25Okapi([tokenize(text) for text in texts])
        return len(self.chunks)


    def keyword_search(self, query: str, limit: int = 10) -> list[tuple[int, float]]:
        if self.bm25 is None or not self.chunks:
            return []
        scores = self.bm25.get_scores(tokenize(query))
        ranked = np.argsort(scores)[::-1]
        return [(int(i), float(scores[i])) for i in ranked[:limit] if scores[i] > 0]

    def vector_search(self, query: str, limit: int = 10) -> list[tuple[int, float]]:
        if self.faiss_index is None:
            return []

        model = self._get_model()
        embedding = model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        embedding = np.asarray(embedding, dtype=np.float32)

        k = min(limit, len(self.chunks))
        scores, indices = self.faiss_index.search(embedding, k)

        return [
            (int(idx), float(score))
            for idx, score in zip(indices[0], scores[0])
            if idx >= 0
        ]

    def hybrid_search(
            self,
            query: str,
            limit_each: int = 10,
            rrf_k: int = 60,
    ) -> list[dict]:
        vector = self.vector_search(query, limit_each)
        keyword = self.keyword_search(query, limit_each)

        fused: dict[int, float] = {}

        # Combine vector and keyword rankings using RRF.
        for ranked_list in (vector, keyword):
            for rank, (idx, _score) in enumerate(ranked_list, start=1):
                chunk_text = self.chunks[idx].text.lower()

                # Skip table-of-contents chunks.
                if (
                        "index" in chunk_text[:100]
                        and "page no." in chunk_text
                        and "introduction" in chunk_text
                        and "references" in chunk_text
                ):
                    continue

                fused[idx] = fused.get(idx, 0.0) + 1.0 / (rrf_k + rank)

        # Give a small bonus to chunks containing the complete query phrase.
        query_phrase = " ".join(tokenize(query))
        if query_phrase:
            for idx in list(fused):
                chunk_text = " ".join(tokenize(self.chunks[idx].text))

                if query_phrase in chunk_text:
                    fused[idx] += 0.02

        ordered = sorted(
            fused.items(),
            key=lambda item: item[1],
            reverse=True,
        )

        return [
            {
                "index": idx,
                "rrf_score": score,
                "chunk": self.chunks[idx],
            }
            for idx, score in ordered
        ]