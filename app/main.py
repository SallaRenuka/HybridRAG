from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import re
from typing import Any

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.config import UPLOAD_DIR, INDEX_DIR
from app.ingest import load_chunks
from app.search_index import HybridIndex, tokenize
from app.retriever import Retriever

INSUFFICIENT_INFO_MESSAGE = "I could not find sufficient information in the uploaded documents."

NEGATION_WORDS = {
    "not", "never", "no", "cannot", "n't", "neither", "nor",
    "incompatible", "unsupported", "without", "disables", "prohibits", "rejects"
}

STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's",
    "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
    "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves",
    "then", "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves"
}

index = HybridIndex()
retriever = Retriever(index=index, use_reranker=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Automatically load persisted index on startup if available
    try:
        if index.load(INDEX_DIR):
            print(f"Loaded existing index with {len(index.chunks)} chunks from {INDEX_DIR}", flush=True)
    except Exception as exc:
        print(f"Failed to load existing index on startup: {exc}", flush=True)
    yield


app = FastAPI(title="HybridRAG Engine", version="0.2.0", lifespan=lifespan)


class QueryRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    top_k: int = Field(default=3, ge=1, le=10)


class Citation(BaseModel):
    id: int
    source: str
    chunk_id: str
    page: int | None = None
    text: str


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    note: str


def extract_claim_tokens(text: str) -> set[str]:
    """Extract informative content tokens from a claim sentence, removing citation tags and stop words."""
    clean = re.sub(r"\[\d+\]", " ", text)
    tokens = tokenize(clean)
    return {t for t in tokens if t not in STOP_WORDS and len(t) > 1}


def check_sentence_support_and_consistency(
    claim_sentence: str,
    chunk_text: str,
    min_overlap: float = 0.35,
) -> bool:
    """Verify semantic support and check for negation polarity contradictions between claim and source."""
    claim_tokens = extract_claim_tokens(claim_sentence)
    if not claim_tokens:
        return True

    # Split chunk into sentences to locate the exact supporting sentence
    chunk_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", chunk_text) if s.strip()]
    if not chunk_sentences:
        chunk_sentences = [chunk_text]

    best_overlap = 0.0
    best_matching_sent = ""

    for c_sent in chunk_sentences:
        c_tokens = set(tokenize(c_sent))
        overlap = len(claim_tokens & c_tokens) / len(claim_tokens)
        if overlap > best_overlap:
            best_overlap = overlap
            best_matching_sent = c_sent

    # If even the best matching sentence does not meet minimum content overlap, reject
    if best_overlap < min_overlap:
        return False

    # Check for negation polarity contradiction between claim and matching chunk sentence
    claim_has_neg = bool(set(tokenize(claim_sentence)) & NEGATION_WORDS)
    match_has_neg = bool(set(tokenize(best_matching_sent)) & NEGATION_WORDS)
    if claim_has_neg != match_has_neg:
        return False

    return True


# Alias for backwards compatibility
verify_claim_support = check_sentence_support_and_consistency


def format_context_and_citation_map(
    results: list[dict],
) -> tuple[str, dict[int, Citation]]:
    """Assign numbered citation IDs [1], [2] to chunks and format structured context."""
    context_blocks = []
    citation_map: dict[int, Citation] = {}

    for idx, item in enumerate(results, start=1):
        chunk = item["chunk"]
        citation = Citation(
            id=idx,
            source=chunk.source,
            chunk_id=chunk.chunk_id,
            page=chunk.page,
            text=chunk.text,
        )
        citation_map[idx] = citation
        page_str = f"Page {chunk.page}" if chunk.page is not None else "Page N/A"
        context_blocks.append(
            f"[{idx}] Source: {chunk.source} | {page_str}\n{chunk.text.strip()}"
        )

    formatted_context = "\n\n".join(context_blocks)
    return formatted_context, citation_map


def process_answer_and_citations(
    raw_answer: str,
    citation_map: dict[int, Citation],
) -> tuple[str, list[Citation]]:
    """Validate every sentence in the response. Remove unsupported claims and invalid citation IDs.
    
    Ensures every factual claim has verified evidence. If no verified sentences remain,
    safely returns the insufficient-information fallback with cleared citations.
    """
    if not raw_answer or INSUFFICIENT_INFO_MESSAGE.lower() in raw_answer.lower():
        return INSUFFICIENT_INFO_MESSAGE, []

    # Split response into sentence units for sentence-level verification
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", raw_answer) if s.strip()]
    if not sentences:
        return INSUFFICIENT_INFO_MESSAGE, []

    verified_sentences: list[str] = []
    verified_citation_ids: set[int] = set()

    for sent in sentences:
        all_cited_raw = re.findall(r"\[(\d+)\]", sent)
        cited_indices = [int(m) for m in all_cited_raw]

        claim_tokens = extract_claim_tokens(sent)
        is_factual = len(claim_tokens) >= 2

        # Every factual sentence MUST have at least one citation
        if is_factual and not cited_indices:
            continue

        # Check for valid citation IDs present in context
        valid_indices = [cid for cid in cited_indices if cid in citation_map]
        if not valid_indices:
            continue

        # Verify semantic evidence support across the valid cited chunks
        sentence_verified_ids = []
        for cid in valid_indices:
            target_chunk = citation_map[cid]
            if check_sentence_support_and_consistency(sent, target_chunk.text):
                sentence_verified_ids.append(cid)

        if not sentence_verified_ids:
            # Claim failed evidence verification or is a contradiction -> drop sentence
            continue

        # Clean sentence so NO invalid or unverified citation IDs remain
        cleaned_text = re.sub(r"\s*\[\d+\]", "", sent).strip()
        tags = "".join(f"[{cid}]" for cid in sorted(set(sentence_verified_ids)))
        if cleaned_text.endswith((".", "!", "?")):
            cleaned_sent = f"{cleaned_text[:-1].rstrip()} {tags}{cleaned_text[-1]}"
        else:
            cleaned_sent = f"{cleaned_text.rstrip()} {tags}."

        verified_sentences.append(cleaned_sent)
        verified_citation_ids.update(sentence_verified_ids)

    # If no sentences passed verification, safely return fallback
    if not verified_sentences or not verified_citation_ids:
        return INSUFFICIENT_INFO_MESSAGE, []

    # Reconstruct answer strictly from verified sentences
    final_answer = " ".join(verified_sentences)

    # Return structured citations for ONLY verified chunks, ordered by citation ID
    final_citations = [
        citation_map[cid]
        for cid in sorted(verified_citation_ids)
    ]

    return final_answer, final_citations


def call_ollama(prompt: str, model_name: str = "llama3.2:3b", timeout: int = 120) -> str:
    """Call local Ollama generation API."""
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": model_name,
            "prompt": prompt,
            "stream": False,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()["response"].strip()


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "indexed_chunks": len(index.chunks)}


@app.post("/ingest")
def ingest() -> dict[str, Any]:
    chunks = load_chunks(UPLOAD_DIR)
    if not chunks:
        raise HTTPException(
            status_code=400,
            detail=f"No supported documents found in {UPLOAD_DIR}. Add PDF, TXT, Markdown, or code files first."
        )
    print(f"Loaded {len(chunks)} chunks. Starting embedding generation...", flush=True)
    count = index.build(chunks)
    index.save(INDEX_DIR)
    print(f"Embedding generation completed and index persisted ({count} chunks).", flush=True)
    return {
        "status": "indexed",
        "files_directory": str(UPLOAD_DIR),
        "chunks_indexed": count,
    }


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    if not index.chunks:
        raise HTTPException(
            status_code=400,
            detail="No documents indexed yet. Add files to data/uploads and call POST /ingest."
        )

    results = retriever.retrieve(request.question, top_k=request.top_k)

    if not results:
        return QueryResponse(
            answer=INSUFFICIENT_INFO_MESSAGE,
            citations=[],
            note="No relevant chunks passed the retrieval and relevance filters."
        )

    formatted_context, citation_map = format_context_and_citation_map(results)

    prompt = f"""You are an accurate, source-grounded assistant. Answer the user's question using ONLY the provided document context below.

Rules:
1. Every factual claim in your answer must be supported by the context and end with its bracketed citation ID (e.g. [1] or [1][2]).
2. Do NOT use outside knowledge. Do NOT invent facts or citations.
3. If the context does not contain enough information to answer the question, respond EXACTLY with:
   "{INSUFFICIENT_INFO_MESSAGE}"
4. Do NOT cite any document ID that does not support the exact sentence.

Document Context:
{formatted_context}

Question: {request.question}

Answer:"""

    try:
        raw_answer = call_ollama(prompt)
        answer, citations = process_answer_and_citations(raw_answer, citation_map)
        note = "Answer generated using local Ollama model with verified document citations."

    except requests.RequestException as exc:
        print(f"Ollama request failed: {exc}", flush=True)
        answer = "Could not generate an AI answer. Please check that Ollama is running."
        citations = []
        note = "Document retrieval succeeded, but Ollama generation failed."

    return QueryResponse(
        answer=answer,
        citations=citations,
        note=note,
    )
