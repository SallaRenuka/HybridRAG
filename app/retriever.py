from __future__ import annotations

import logging
from typing import Sequence

from app.config import RERANKER_MODEL
from app.search_index import HybridIndex, tokenize

logger = logging.getLogger(__name__)


def compute_jaccard_similarity(tokens_a: set[str], tokens_b: set[str]) -> float:
    """Compute token-level Jaccard similarity between two token sets."""
    if not tokens_a or not tokens_b:
        return 0.0
    union_len = len(tokens_a | tokens_b)
    if union_len == 0:
        return 0.0
    return len(tokens_a & tokens_b) / union_len


class Retriever:
    def __init__(
        self,
        index: HybridIndex,
        use_reranker: bool = True,
        default_score_threshold: float | None = None,
        max_chunks_per_source_page: int | None = 2,
        similarity_threshold: float = 0.75,
    ):
        self.index = index
        self.use_reranker = use_reranker
        self.default_score_threshold = default_score_threshold
        self.max_chunks_per_source_page = max_chunks_per_source_page
        self.similarity_threshold = similarity_threshold
        self._reranker = None

    def _get_reranker(self):
        if self._reranker is None:
            from sentence_transformers import CrossEncoder

            self._reranker = CrossEncoder(
                RERANKER_MODEL,
                device="cpu",
            )

        return self._reranker

    def deduplicate_and_diversify(
        self,
        candidates: list[dict],
        top_k: int = 3,
        score_threshold: float | None = None,
        max_per_source_page: int | None = None,
        similarity_threshold: float | None = None,
    ) -> list[dict]:
        """Filter out redundant chunks while preserving diverse evidence across pages and documents."""
        if not candidates:
            return []

        threshold = score_threshold if score_threshold is not None else self.default_score_threshold
        page_quota = max_per_source_page if max_per_source_page is not None else self.max_chunks_per_source_page
        sim_cutoff = similarity_threshold if similarity_threshold is not None else self.similarity_threshold

        selected: list[dict] = []
        source_page_counts: dict[tuple[str, int | None], int] = {}
        token_cache: list[set[str]] = []

        for item in candidates:
            # Configurable relevance score cutoff
            if threshold is not None:
                score = item.get("rerank_score")
                if score is not None and score < threshold:
                    continue

            chunk = item["chunk"]
            key = (chunk.source, chunk.page)

            # Prevent a single page from overcrowding top-k results
            if page_quota is not None and source_page_counts.get(key, 0) >= page_quota:
                continue

            chunk_tokens = set(tokenize(chunk.text))
            if not chunk_tokens:
                continue

            # Check for redundancy against already selected chunks
            is_redundant = False
            for idx, existing in enumerate(selected):
                existing_chunk = existing["chunk"]
                existing_key = (existing_chunk.source, existing_chunk.page)
                existing_tokens = token_cache[idx]

                jaccard = compute_jaccard_similarity(chunk_tokens, existing_tokens)

                # Same source+page with high overlap (sliding window redundancy)
                if key == existing_key and jaccard >= sim_cutoff:
                    is_redundant = True
                    break

                # Near-identical boilerplate (>92% overlap) across different pages
                if jaccard >= 0.92:
                    is_redundant = True
                    break

            if not is_redundant:
                selected.append(item)
                token_cache.append(chunk_tokens)
                source_page_counts[key] = source_page_counts.get(key, 0) + 1

            if len(selected) >= top_k:
                break

        return selected

    def retrieve(
        self,
        question: str,
        top_k: int = 3,
        candidate_k: int = 20,
        score_threshold: float | None = None,
        max_chunks_per_source_page: int | None = None,
    ) -> list[dict]:
        if not question.strip():
            return []

        candidates = self.index.hybrid_search(
            question,
            limit_each=candidate_k,
        )

        if not candidates:
            return []

        if self.use_reranker:
            try:
                model = self._get_reranker()

                pairs = [
                    [question, item["chunk"].text]
                    for item in candidates
                ]

                scores = model.predict(pairs)

                for item, score in zip(candidates, scores):
                    item["rerank_score"] = float(score)

                candidates.sort(
                    key=lambda item: item["rerank_score"],
                    reverse=True,
                )

            except Exception as exc:
                logger.warning(f"Cross-Encoder unavailable; using RRF ranking: {exc}")

        return self.deduplicate_and_diversify(
            candidates,
            top_k=top_k,
            score_threshold=score_threshold,
            max_per_source_page=max_chunks_per_source_page,
        )
