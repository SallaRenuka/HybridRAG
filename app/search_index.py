from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime, timezone
import re
from typing import Sequence

import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from app.config import EMBEDDING_MODEL, INDEX_DIR
from app.ingest import Chunk

INDEX_SCHEMA_VERSION = 1
INDEX_METADATA_FILENAME = "metadata.json"
FAISS_INDEX_FILENAME = "faiss.index"


def tokenize(text: str) -> list[str]:
    # Keeps useful code identifiers and error codes together while stripping trailing sentence punctuation.
    tokens = re.findall(r"[A-Za-z0-9_./:-]+", text.lower())
    return [t.strip(".,;:!?") for t in tokens if t.strip(".,;:!?")]


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

    def save(self, directory: Path | str = INDEX_DIR) -> bool:
        """Persist FAISS index and chunk metadata to disk safely using atomic file replacement."""
        if self.faiss_index is None or not self.chunks:
            return False

        target_dir = Path(directory)
        target_dir.mkdir(parents=True, exist_ok=True)

        meta_file = target_dir / INDEX_METADATA_FILENAME
        faiss_file = target_dir / FAISS_INDEX_FILENAME
        tmp_meta_file = target_dir / f"{INDEX_METADATA_FILENAME}.tmp"
        tmp_faiss_file = target_dir / f"{FAISS_INDEX_FILENAME}.tmp"

        metadata = {
            "schema_version": INDEX_SCHEMA_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "embedding_model": self.embedding_model_name,
            "chunk_count": len(self.chunks),
            "chunks": [c.to_dict() for c in self.chunks],
        }

        try:
            # 1. Write FAISS index to temporary file
            faiss.write_index(self.faiss_index, str(tmp_faiss_file))

            # 2. Write metadata JSON to temporary file
            with open(tmp_meta_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)

            # 3. Atomically replace existing files with verified temp files
            os.replace(str(tmp_faiss_file), str(faiss_file))
            os.replace(str(tmp_meta_file), str(meta_file))
            return True
        except Exception as exc:
            # Clean up temporary files on write failure
            if tmp_faiss_file.exists():
                tmp_faiss_file.unlink(missing_ok=True)
            if tmp_meta_file.exists():
                tmp_meta_file.unlink(missing_ok=True)
            raise IOError(f"Failed to persist index to {target_dir}: {exc}") from exc

    def load(self, directory: Path | str = INDEX_DIR) -> bool:
        """Load persisted index and reconstruct BM25 safely without pickle deserialization."""
        target_dir = Path(directory)
        meta_file = target_dir / INDEX_METADATA_FILENAME
        faiss_file = target_dir / FAISS_INDEX_FILENAME

        if not meta_file.exists() or not faiss_file.exists():
            return False

        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                metadata = json.load(f)

            if not isinstance(metadata, dict):
                return False

            # Validate schema version
            if metadata.get("schema_version") != INDEX_SCHEMA_VERSION:
                return False

            # Validate embedding model compatibility
            if metadata.get("embedding_model") != self.embedding_model_name:
                return False

            raw_chunks = metadata.get("chunks")
            if not isinstance(raw_chunks, list):
                return False

            chunks = [
                Chunk(
                    chunk_id=c["chunk_id"],
                    text=c["text"],
                    source=c["source"],
                    page=c.get("page"),
                )
                for c in raw_chunks
            ]

            if len(chunks) != metadata.get("chunk_count"):
                return False

            # Read native FAISS binary index
            loaded_faiss = faiss.read_index(str(faiss_file))
            if loaded_faiss.ntotal != len(chunks):
                return False

            # Deterministically rebuild BM25Okapi from loaded chunks
            texts = [c.text for c in chunks]
            loaded_bm25 = BM25Okapi([tokenize(text) for text in texts])

            self.chunks = chunks
            self.faiss_index = loaded_faiss
            self.bm25 = loaded_bm25
            return True
        except Exception:
            return False


    def keyword_search(self, query: str, limit: int = 10) -> list[tuple[int, float]]:
        if self.bm25 is None or not self.chunks or not query.strip():
            return []
        tokens = tokenize(query)
        if not tokens:
            return []
        scores = self.bm25.get_scores(tokens)
        ranked = np.argsort(scores)[::-1]
        return [(int(i), float(scores[i])) for i in ranked[:limit] if scores[i] > 0]

    def vector_search(self, query: str, limit: int = 10) -> list[tuple[int, float]]:
        if self.faiss_index is None or not self.chunks or not query.strip():
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
        if not query.strip():
            return []

        vector = self.vector_search(query, limit_each)
        keyword = self.keyword_search(query, limit_each)

        fused: dict[int, float] = {}

        # Pure Reciprocal Rank Fusion across vector and keyword rankings
        for ranked_list in (vector, keyword):
            for rank, (idx, _score) in enumerate(ranked_list, start=1):
                fused[idx] = fused.get(idx, 0.0) + 1.0 / (rrf_k + rank)

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