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

    def build(self, chunks: Sequence[Chunk]) -> int:
        self.chunks = list(chunks)

        if not self.chunks:
            self.faiss_index = None
            self.bm25 = None
            return 0

        texts = [c.text for c in self.chunks]
        print("Total chunks:", len(texts), flush=True)
        print("Invalid chunks:", sum(not isinstance(t, str) or not t.strip() for t in texts), flush=True)
        print("Sample type:", type(texts[0]) if texts else "No chunks", flush=True)

        print("Loading embedding model...", flush=True)
        model = self._get_model()

        print("Generating embeddings...", flush=True)
        print("First chunk:", repr(texts[0][:100]), flush=True)
        print("Input type:", type(texts[0]), flush=True)


        import torch
        torch.set_num_threads(1)
        embeddings_list = []

        for i, text in enumerate(texts):
            try:
                embedding = model.encode(
                    [text],
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                )
                embeddings_list.append(embedding[0])

            except Exception as exc:
                print(f"Embedding failed at chunk {i}: {exc}", flush=True)
                raise

        embeddings = np.asarray(embeddings_list, dtype=np.float32)



        embeddings = np.asarray(embeddings, dtype=np.float32)

        print("Building FAISS index...", flush=True)
        self.faiss_index = faiss.IndexFlatIP(embeddings.shape[1])
        self.faiss_index.add(embeddings)

        print("Building keyword index...", flush=True)
        self.bm25 = BM25Okapi([tokenize(text) for text in texts])

        print("Index building completed.", flush=True)
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