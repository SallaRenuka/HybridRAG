from __future__ import annotations

import logging
import threading
from typing import Any, Sequence

from app.config import RERANKER_MODEL
from app.search_index import HybridIndex, tokenize

logger = logging.getLogger(__name__)


_SHARED_RERANKERS: dict[str, Any] = {}
_RERANKER_LOCK = threading.Lock()
_RERANK_INFERENCE_LOCK = threading.Lock()


def compute_jaccard_similarity(tokens_a: set[str], tokens_b: set[str]) -> float:
    """Compute token-level Jaccard similarity between two token sets."""
    if not tokens_a or not tokens_b:
        return 0.0
    union_len = len(tokens_a | tokens_b)
    if union_len == 0:
        return 0.0
    return len(tokens_a & tokens_b) / union_len


class Retriever:
    """Two-stage Hybrid Information Retriever with Neural Cross-Encoder Reranking and Deduplication.

    Calibration Procedure for Cross-Encoder Relevance Threshold:
    ------------------------------------------------------------
    The Cross-Encoder (ms-marco-MiniLM-L-6-v2) outputs unbounded logit scores representing
    unnormalized log-odds of relevance:
    - Highly relevant passages: typically score > 0.0 to +8.0.
    - Weak / borderline passages: typically score between -3.0 and 0.0.
    - Completely irrelevant / out-of-domain text: typically scores < -4.0 to -11.0.

    To calibrate the threshold for a specific deployment or dataset:
    1. Collect a small set (e.g. 20-50) of domain queries with known relevant passages and
       unrelated negative passages.
    2. Run CrossEncoder.predict() on all pairs and record score distributions.
    3. Determine the F1-optimal threshold (typically around -3.0 to -2.0) that filters out
       unrelated content without dropping valid answers.
    4. Pass the calibrated threshold via `default_score_threshold` or use adaptive relative
       margin thresholding via `dynamic_margin` (e.g. candidate must score >= top_score - margin).
    5. If reranking is unavailable (e.g. missing weights, device error, or memory exhaustion),
       the retriever automatically falls back to Reciprocal Rank Fusion (RRF) scores without crashing.
    """

    def __init__(
        self,
        index: HybridIndex,
        use_reranker: bool = True,
        default_score_threshold: float | None = None,
        default_dynamic_margin: float | None = None,
        max_chunks_per_source_page: int | None = 2,
        similarity_threshold: float = 0.75,
    ):
        self.index = index
        self.use_reranker = use_reranker
        self.default_score_threshold = default_score_threshold
        self.default_dynamic_margin = default_dynamic_margin
        self.max_chunks_per_source_page = max_chunks_per_source_page
        self.similarity_threshold = similarity_threshold
        self._reranker = None

    def _get_reranker(self):
        if self._reranker is None:
            with _RERANKER_LOCK:
                if RERANKER_MODEL not in _SHARED_RERANKERS:
                    from sentence_transformers import CrossEncoder
                    try:
                        _SHARED_RERANKERS[RERANKER_MODEL] = CrossEncoder(
                            RERANKER_MODEL,
                            device="cpu",
                            local_files_only=True,
                        )
                    except Exception:
                        _SHARED_RERANKERS[RERANKER_MODEL] = CrossEncoder(
                            RERANKER_MODEL,
                            device="cpu",
                        )
                self._reranker = _SHARED_RERANKERS[RERANKER_MODEL]

        return self._reranker

    def deduplicate_and_diversify(
        self,
        candidates: list[dict],
        top_k: int = 3,
        score_threshold: float | None = None,
        dynamic_margin: float | None = None,
        max_per_source_page: int | None = None,
        similarity_threshold: float | None = None,
    ) -> list[dict]:
        """Filter out redundant chunks while preserving diverse evidence across pages and documents."""
        if not candidates:
            return []

        threshold = score_threshold if score_threshold is not None else self.default_score_threshold
        margin = dynamic_margin if dynamic_margin is not None else self.default_dynamic_margin
        page_quota = max_per_source_page if max_per_source_page is not None else self.max_chunks_per_source_page
        sim_cutoff = similarity_threshold if similarity_threshold is not None else self.similarity_threshold

        # Compute dynamic score threshold relative to top candidate if margin is configured
        top_score = candidates[0].get("rerank_score")
        if margin is not None and top_score is not None:
            relative_cutoff = top_score - margin
            threshold = max(threshold, relative_cutoff) if threshold is not None else relative_cutoff

        selected: list[dict] = []
        source_page_counts: dict[tuple[str, int | None], int] = {}
        token_cache: list[set[str]] = []

        for item in candidates:
            # Configurable relevance score cutoff
            score = item.get("rerank_score")
            if threshold is not None and score is not None and score < threshold:
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
        candidate_k: int = 35,
        score_threshold: float | None = None,
        dynamic_margin: float | None = None,
        max_chunks_per_source_page: int | None = None,
    ) -> list[dict]:
        if not question.strip():
            return []

        import re
        q_ids = re.findall(r"\b([A-Za-z]{2,5}\d{2,6})\b", question, re.IGNORECASE)
        is_employee_query = bool(q_ids or re.search(r"\b(?:employee|employees|staff|job role|projects completed|highest experience|top \d+ employees)\b", question, re.IGNORECASE))

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

                with _RERANK_INFERENCE_LOCK:
                    scores = model.predict(pairs)

                for item, score in zip(candidates, scores):
                    boost = 0.0
                    c_text = item["chunk"].text
                    if q_ids:
                        for q_id in q_ids:
                            if re.search(r"\b" + re.escape(q_id) + r"\b", c_text, re.IGNORECASE):
                                boost += 10.0
                    elif is_employee_query:
                        if "Employee_Database" in item["chunk"].source or "EMP" in c_text:
                            boost += 5.0
                    item["rerank_score"] = float(score) + boost

                candidates.sort(
                    key=lambda item: item["rerank_score"],
                    reverse=True,
                )

            except Exception as exc:
                logger.warning(f"Cross-Encoder reranking failed ({exc}); falling back to Reciprocal Rank Fusion.")
                # Fallback: maintain candidate order based on RRF scores
                for item in candidates:
                    boost = 0.0
                    c_text = item["chunk"].text
                    if q_ids:
                        for q_id in q_ids:
                            if re.search(r"\b" + re.escape(q_id) + r"\b", c_text, re.IGNORECASE):
                                boost += 1.0
                    elif is_employee_query and ("Employee_Database" in item["chunk"].source or "EMP" in c_text):
                        boost += 0.5
                    item["rerank_score"] = None
                    item["rrf_score"] = item.get("rrf_score", 0.0) + boost
                candidates.sort(
                    key=lambda item: item.get("rrf_score", 0.0),
                    reverse=True,
                )

        return self.deduplicate_and_diversify(
            candidates,
            top_k=top_k,
            score_threshold=score_threshold,
            dynamic_margin=dynamic_margin,
            max_per_source_page=max_chunks_per_source_page,
        )
