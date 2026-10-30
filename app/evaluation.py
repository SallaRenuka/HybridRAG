from __future__ import annotations

from dataclasses import dataclass, asdict
import re
from typing import Sequence

from app.main import Citation, INSUFFICIENT_INFO_MESSAGE, check_sentence_support_and_consistency, extract_claim_tokens
from app.retriever import Retriever


@dataclass
class EvalSample:
    """Evaluation test case.
    
    Attributes:
        query: User question to evaluate.
        expected_chunk_ids: Human-verified ground-truth chunk IDs that contain the answer.
        expected_sources: Human-verified ground-truth filenames (or pages) containing the answer.
        is_answerable: True if documents contain sufficient information; False if unanswerable.
        reference_answer: Optional human-written reference answer for comparison.
    """
    query: str
    expected_chunk_ids: list[str]
    expected_sources: list[str]
    is_answerable: bool = True
    reference_answer: str | None = None


@dataclass
class EvaluationReport:
    """Evaluation summary explicitly distinguishing human-verified ground truth metrics from automated heuristics.

    Ground-Truth Metrics:
        - ground_truth_mrr: Mean Reciprocal Rank against human-verified relevant chunk IDs.
        - ground_truth_recall_at_1: Percentage of queries where rank #1 matches human ground truth.
        - ground_truth_recall_at_k: Percentage of queries where target chunk is in top K results.
        - ground_truth_citation_precision: Ratio of returned citations matching human ground-truth sources.
        - ground_truth_citation_recall: Ratio of human ground-truth sources cited in the response.
        - ground_truth_no_answer_accuracy: Accuracy of correctly refusing unanswerable questions.

    Automated Heuristic Metrics:
        - automated_claim_faithfulness: Percentage of generated factual sentences supported by citations without contradiction.
        - automated_citation_support_ratio: Percentage of returned citations actively supporting at least one claim.
    """
    total_queries: int
    ground_truth_mrr: float
    ground_truth_recall_at_1: float
    ground_truth_recall_at_k: float
    ground_truth_citation_precision: float
    ground_truth_citation_recall: float
    ground_truth_no_answer_accuracy: float
    automated_claim_faithfulness: float
    automated_citation_support_ratio: float

    def to_dict(self):
        return asdict(self)


def compute_recall_at_k(retrieved_ids: list[str], expected_ids: list[str], k: int) -> float:
    """Compute Recall@K against human-verified ground-truth chunk IDs."""
    if not expected_ids:
        return 1.0 if not retrieved_ids else 0.0
    top_k_retrieved = set(retrieved_ids[:k])
    expected_set = set(expected_ids)
    hits = len(top_k_retrieved & expected_set)
    return hits / len(expected_set)


def compute_reciprocal_rank(retrieved_ids: list[str], expected_ids: list[str]) -> float:
    """Compute Reciprocal Rank (RR): 1 / rank of the first human-verified relevant chunk."""
    if not expected_ids:
        return 1.0 if not retrieved_ids else 0.0
    expected_set = set(expected_ids)
    for rank, cid in enumerate(retrieved_ids, start=1):
        if cid in expected_set:
            return 1.0 / rank
    return 0.0


def compute_citation_metrics(
    returned_citations: list[Citation],
    expected_sources: list[str],
) -> tuple[float, float]:
    """Compute Citation Precision and Recall against human-verified expected source files."""
    returned_source_set = {c.source for c in returned_citations}
    expected_source_set = set(expected_sources)

    if not expected_source_set:
        prec = 1.0 if not returned_source_set else 0.0
        rec = 1.0 if not returned_source_set else 0.0
        return prec, rec

    if not returned_source_set:
        return 0.0, 0.0

    hits = len(returned_source_set & expected_source_set)
    precision = hits / len(returned_source_set)
    recall = hits / len(expected_source_set)
    return precision, recall


def compute_automated_faithfulness(
    answer: str,
    citations: list[Citation],
) -> float:
    """Automated heuristic evaluating whether every factual sentence is grounded in citations without contradiction."""
    if not answer or INSUFFICIENT_INFO_MESSAGE.lower() in answer.lower():
        return 1.0

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", answer) if s.strip()]
    if not sentences:
        return 1.0

    citation_lookup = {c.id: c.text for c in citations}
    supported_sentences = 0
    factual_sentences = 0

    for sent in sentences:
        claim_tokens = extract_claim_tokens(sent)
        if len(claim_tokens) < 2:
            continue

        factual_sentences += 1
        cited_ids = [int(m) for m in re.findall(r"\[(\d+)\]", sent)]
        if not cited_ids:
            continue

        is_supported = any(
            check_sentence_support_and_consistency(sent, citation_lookup[cid])
            for cid in cited_ids
            if cid in citation_lookup
        )
        if is_supported:
            supported_sentences += 1

    if factual_sentences == 0:
        return 1.0

    return supported_sentences / factual_sentences


# Backwards compatibility alias
compute_answer_faithfulness = compute_automated_faithfulness


def evaluate_retrieval(
    samples: Sequence[EvalSample],
    retriever: Retriever,
    top_k: int = 3,
) -> dict[str, float]:
    """Evaluate retrieval engine against human-verified ground-truth datasets."""
    recalls_1 = []
    recalls_k = []
    rrs = []

    for sample in samples:
        if not sample.is_answerable:
            continue

        results = retriever.retrieve(sample.query, top_k=top_k)
        retrieved_ids = [item["chunk"].chunk_id for item in results]

        r1 = compute_recall_at_k(retrieved_ids, sample.expected_chunk_ids, k=1)
        rk = compute_recall_at_k(retrieved_ids, sample.expected_chunk_ids, k=top_k)
        rr = compute_reciprocal_rank(retrieved_ids, sample.expected_chunk_ids)

        recalls_1.append(r1)
        recalls_k.append(rk)
        rrs.append(rr)

    return {
        "ground_truth_recall_at_1": sum(recalls_1) / len(recalls_1) if recalls_1 else 0.0,
        f"ground_truth_recall_at_{top_k}": sum(recalls_k) / len(recalls_k) if recalls_k else 0.0,
        "ground_truth_mrr": sum(rrs) / len(rrs) if rrs else 0.0,
        "mean_recall_at_1": sum(recalls_1) / len(recalls_1) if recalls_1 else 0.0,
        f"mean_recall_at_{top_k}": sum(recalls_k) / len(recalls_k) if recalls_k else 0.0,
        "mean_mrr": sum(rrs) / len(rrs) if rrs else 0.0,
        "evaluated_queries": len(recalls_1),
    }
