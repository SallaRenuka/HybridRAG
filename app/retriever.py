from __future__ import annotations

from app.config import RERANKER_MODEL
from app.search_index import HybridIndex


class Retriever:
    def __init__(self, index: HybridIndex, use_reranker: bool = True):
        self.index = index
        self.use_reranker = use_reranker
        self._reranker = None

    def _get_reranker(self):
        if self._reranker is None:
            from sentence_transformers import CrossEncoder

            self._reranker = CrossEncoder(
                RERANKER_MODEL,
                device="cpu",
            )

        return self._reranker

    def retrieve(
        self,
        question: str,
        top_k: int = 3,
        candidate_k: int = 20,
    ) -> list[dict]:
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

                print("\n--- TOP RERANKED CANDIDATES ---", flush=True)

                for rank, item in enumerate(candidates[:5], start=1):
                    chunk = item["chunk"]

                    print(
                        f"Rank {rank} | Page {chunk.page} | "
                        f"Score {item['rerank_score']:.4f}",
                        flush=True,
                    )
                    print(chunk.text[:180].replace("\n", " "), flush=True)

                print("--- END RERANKED CANDIDATES ---\n", flush=True)

            except Exception as exc:
                print(
                    f"Cross-Encoder unavailable; using RRF ranking: {exc}",
                    flush=True,
                )

        return candidates[:top_k]

