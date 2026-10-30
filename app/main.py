from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import requests

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.config import UPLOAD_DIR, INDEX_DIR
from app.ingest import load_chunks
from app.search_index import HybridIndex
from app.retriever import Retriever

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


app = FastAPI(title="HybridRAG Engine", version="0.1.0", lifespan=lifespan)


class QueryRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    top_k: int = Field(default=3, ge=1, le=10)


class Citation(BaseModel):
    source: str
    chunk_id: str
    page: int | None = None
    text: str


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    note: str


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
    print("\n--- RETRIEVAL DEBUG ---", flush=True)

    for rank, item in enumerate(results, start=1):
        chunk = item["chunk"]

        print(f"\nRank: {rank}", flush=True)
        print(f"Source: {chunk.source}", flush=True)
        print(f"Page: {chunk.page}", flush=True)
        print(f"RRF score: {item.get('rrf_score')}", flush=True)
        print(f"Rerank score: {item.get('rerank_score')}", flush=True)
        print(f"Text preview: {chunk.text[:250]!r}", flush=True)

    print("--- END DEBUG ---\n", flush=True)

    if not results:
        return QueryResponse(
            answer="I don't know based on the available documents.",
            citations=[],
            note="No relevant chunks were found."
        )
    citations = [
        Citation(
            source=item["chunk"].source,
            chunk_id=item["chunk"].chunk_id,
            page=item["chunk"].page,
            text=item["chunk"].text,
        )
        for item in results
        if not (
                "index" in item["chunk"].text.lower()[:100]
                and "page no." in item["chunk"].text.lower()
        )
    ]



    context = "\n\n".join(
        f"Source: {item['chunk'].source}\n"
        f"Page: {item['chunk'].page}\n"
        f"{item['chunk'].text.replace(chr(10), ' ').replace(chr(13), ' ')}"
        for item in results
    )


    prompt = f"""Answer the question using only the provided document context.
If the answer is not present in the context, say you don't know based on the documents.
Do not invent facts.

Document context:
{context}

Question: {request.question}

Answer:"""

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.2:3b",
                "prompt": prompt,
                "stream": False,
            },
            timeout=120,
        )
        response.raise_for_status()
        answer = response.json()["response"].strip()
        note = "Answer generated using local Ollama model with retrieved document context."

    except requests.RequestException as exc:
        print(f"Ollama request failed: {exc}", flush=True)
        answer = "Could not generate an AI answer. Please check that Ollama is running."
        note = "Document retrieval succeeded, but Ollama generation failed."

    return QueryResponse(
        answer=answer,
        citations=citations,
        note=note,
    )