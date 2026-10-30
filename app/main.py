from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any

from fastapi import Depends, FastAPI, File, HTTPException, Security, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
import requests

from app.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    TokenResponse,
    hash_password,
    verify_password,
    create_user_session,
    get_current_user,
    security,
    db,
)
from app.config import (
    UPLOAD_DIR,
    INDEX_DIR,
    SUPPORTED_EXTENSIONS,
    get_user_upload_dir,
    get_user_index_dir,
)
from app.database import User, DocumentRecord, ConversationRecord, MessageRecord
from app.ingest import load_chunks
from app.retriever import Retriever
from app.search_index import HybridIndex, tokenize
from app.workspace import workspace_manager, compute_file_sha256

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

# Default global index/retriever for backward compatibility
default_index, default_retriever = workspace_manager.get_default_workspace()
index = default_index
retriever = default_retriever


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Automatically load persisted index on startup if available
    try:
        if default_index.load(INDEX_DIR):
            print(f"Loaded existing index with {len(default_index.chunks)} chunks from {INDEX_DIR}", flush=True)
    except Exception as exc:
        print(f"Failed to load existing index on startup: {exc}", flush=True)
    yield


app = FastAPI(
    title="HybridRAG Enterprise Engine",
    version="1.0.0",
    description="Enterprise-grade Document Intelligence and Question Answering Platform with User Isolation and Authentication",
    lifespan=lifespan,
)


# ------------------ Request & Response Schemas ------------------
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


class CreateConversationRequest(BaseModel):
    title: str = Field(default="New Conversation", min_length=1, max_length=255)


class SendMessageRequest(BaseModel):
    message: str = Field(min_length=2, max_length=2000)
    top_k: int = Field(default=3, ge=1, le=10)


# ------------------ Claim & Citation Verification Helpers ------------------
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

    if best_overlap < min_overlap:
        return False

    claim_has_neg = bool(set(tokenize(claim_sentence)) & NEGATION_WORDS)
    match_has_neg = bool(set(tokenize(best_matching_sent)) & NEGATION_WORDS)
    if claim_has_neg != match_has_neg:
        return False

    return True


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
    """Validate every sentence in the response. Remove unsupported claims and invalid citation IDs."""
    if not raw_answer or INSUFFICIENT_INFO_MESSAGE.lower() in raw_answer.lower():
        return INSUFFICIENT_INFO_MESSAGE, []

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

        if is_factual and not cited_indices:
            continue

        valid_indices = [cid for cid in cited_indices if cid in citation_map]
        if not valid_indices:
            continue

        sentence_verified_ids = []
        for cid in valid_indices:
            target_chunk = citation_map[cid]
            if check_sentence_support_and_consistency(sent, target_chunk.text):
                sentence_verified_ids.append(cid)

        if not sentence_verified_ids:
            continue

        cleaned_text = re.sub(r"\s*\[\d+\]", "", sent).strip()
        tags = "".join(f"[{cid}]" for cid in sorted(set(sentence_verified_ids)))
        if cleaned_text.endswith((".", "!", "?")):
            cleaned_sent = f"{cleaned_text[:-1].rstrip()} {tags}{cleaned_text[-1]}"
        else:
            cleaned_sent = f"{cleaned_text.rstrip()} {tags}."

        verified_sentences.append(cleaned_sent)
        verified_citation_ids.update(sentence_verified_ids)

    if not verified_sentences or not verified_citation_ids:
        return INSUFFICIENT_INFO_MESSAGE, []

    final_answer = " ".join(verified_sentences)
    final_citations = [citation_map[cid] for cid in sorted(verified_citation_ids)]
    return final_answer, final_citations


def call_ollama(prompt: str, model_name: str = "llama3.2:3b", timeout: int = 120) -> str:
    """Call local Ollama generation API."""
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": model_name, "prompt": prompt, "stream": False},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()["response"].strip()


# ------------------ Authentication Endpoints ------------------
@app.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(request: UserRegisterRequest) -> UserResponse:
    existing_user = db.get_user_by_email(request.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    # Cryptographically secure password hashing (scrypt)
    pw_hash = hash_password(request.password)
    user = db.create_user(email=request.email, password_hash=pw_hash)

    # Initialize user's isolated workspace directories
    get_user_upload_dir(user.id)
    get_user_index_dir(user.id)

    return UserResponse(id=user.id, email=user.email, created_at=user.created_at)


@app.post("/auth/login", response_model=TokenResponse)
def login(request: UserLoginRequest) -> TokenResponse:
    user = db.get_user_by_email(request.email)
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_user_session(db, user_id=user.id)
    return TokenResponse(access_token=token, token_type="bearer", expires_in_hours=24)


@app.post("/auth/logout")
def logout(credentials: HTTPAuthorizationCredentials = Security(security), current_user: User = Depends(get_current_user)) -> dict[str, str]:
    if credentials and credentials.credentials:
        db.revoke_session(credentials.credentials)
    return {"status": "logged_out", "message": "Session successfully terminated."}


@app.get("/auth/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(id=current_user.id, email=current_user.email, created_at=current_user.created_at)


# ------------------ User Document Management Endpoints ------------------
@app.get("/documents")
def list_documents(current_user: User = Depends(get_current_user)) -> list[dict[str, Any]]:
    docs = db.get_user_documents(current_user.id)
    return [
        {
            "id": doc.id,
            "filename": doc.filename,
            "file_size_bytes": doc.file_size_bytes,
            "chunk_count": doc.chunk_count,
            "created_at": doc.created_at,
        }
        for doc in docs
    ]


@app.get("/documents/{document_id}")
def get_document(document_id: int, current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    # Strictly enforce user ownership & data isolation
    doc = db.get_user_document_by_id(document_id, current_user.id)
    if not doc:
        # Check if document exists under another user to distinguish 403 Forbidden vs 404 Not Found
        with db.get_connection() as conn:
            exists = conn.execute("SELECT id, user_id FROM documents WHERE id = ?", (document_id,)).fetchone()
            if exists:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: You do not have permission to view documents belonging to another user.",
                )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    return {
        "id": doc.id,
        "filename": doc.filename,
        "file_size_bytes": doc.file_size_bytes,
        "chunk_count": doc.chunk_count,
        "created_at": doc.created_at,
    }


@app.post("/documents/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    file_ext = Path(file.filename or "").suffix.lower()
    if file_ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{file_ext}'. Allowed formats: {sorted(SUPPORTED_EXTENSIONS)}",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    file_hash = compute_file_sha256(content)
    user_upload_dir = get_user_upload_dir(current_user.id)
    safe_filename = Path(file.filename).name
    destination = user_upload_dir / safe_filename

    # Save to user's isolated storage
    with open(destination, "wb") as f:
        f.write(content)

    doc_record = db.create_document(
        user_id=current_user.id,
        filename=safe_filename,
        file_hash=file_hash,
        file_size_bytes=len(content),
    )

    return {
        "status": "uploaded",
        "document_id": doc_record.id,
        "filename": doc_record.filename,
        "file_size_bytes": doc_record.file_size_bytes,
    }


# ------------------ Chat & Conversation Endpoints ------------------
@app.post("/chat/conversations", status_code=status.HTTP_201_CREATED)
def create_conversation(
    request: CreateConversationRequest,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    conv = db.create_conversation(user_id=current_user.id, title=request.title)
    return {"id": conv.id, "title": conv.title, "created_at": conv.created_at}


@app.get("/chat/conversations")
def list_conversations(current_user: User = Depends(get_current_user)) -> list[dict[str, Any]]:
    convs = db.get_user_conversations(current_user.id)
    return [{"id": c.id, "title": c.title, "created_at": c.created_at, "updated_at": c.updated_at} for c in convs]


@app.get("/chat/conversations/{conversation_id}")
def get_conversation_history(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    conv = db.get_conversation_by_id(conversation_id, current_user.id)
    if not conv:
        with db.get_connection() as conn:
            exists = conn.execute("SELECT id FROM chat_conversations WHERE id = ?", (conversation_id,)).fetchone()
            if exists:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: You do not have permission to view conversations belonging to another user.",
                )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    messages = db.get_messages_for_conversation(conversation_id, current_user.id)
    return {
        "conversation_id": conv.id,
        "title": conv.title,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "citations": json.loads(m.citations_json) if m.citations_json else [],
                "created_at": m.created_at,
            }
            for m in messages
        ],
    }


@app.post("/chat/conversations/{conversation_id}/messages", response_model=QueryResponse)
def send_chat_message(
    conversation_id: int,
    request: SendMessageRequest,
    current_user: User = Depends(get_current_user),
) -> QueryResponse:
    conv = db.get_conversation_by_id(conversation_id, current_user.id)
    if not conv:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: You do not own this conversation.")

    # Record user message in DB
    db.add_chat_message(conversation_id, current_user.id, role="user", content=request.message)

    # Query strictly within current user's isolated workspace
    user_index, user_retriever = workspace_manager.get_user_workspace(current_user.id)
    if not user_index.chunks:
        answer = INSUFFICIENT_INFO_MESSAGE
        citations = []
        note = "No documents indexed in your workspace."
    else:
        results = user_retriever.retrieve(request.message, top_k=request.top_k)
        if not results:
            answer = INSUFFICIENT_INFO_MESSAGE
            citations = []
            note = "No relevant chunks passed retrieval threshold."
        else:
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

Question: {request.message}

Answer:"""
            try:
                raw_ans = call_ollama(prompt)
                answer, citations = process_answer_and_citations(raw_ans, citation_map)
                note = "Answer generated using local Ollama model with verified document citations."
            except requests.RequestException:
                answer = "Could not generate an AI answer. Please check that Ollama is running."
                citations = []
                note = "Retrieval succeeded, but generation failed."

    # Record assistant message in DB with citations
    citations_data = [c.model_dump() for c in citations]
    db.add_chat_message(
        conversation_id=conversation_id,
        user_id=current_user.id,
        role="assistant",
        content=answer,
        citations_json=json.dumps(citations_data),
    )

    return QueryResponse(answer=answer, citations=citations, note=note)


# ------------------ Ingest & Query Endpoints (Multi-tenant & Legacy Compatible) ------------------
@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "indexed_chunks": len(default_index.chunks)}


@app.post("/ingest")
def ingest(credentials: HTTPAuthorizationCredentials | None = Security(security)) -> dict[str, Any]:
    # If authenticated, ingest strictly for the authenticated user
    if credentials and credentials.credentials:
        try:
            current_user = get_current_user(credentials)
            count = workspace_manager.ingest_user_documents(current_user.id)
            return {
                "status": "indexed",
                "user_id": current_user.id,
                "chunks_indexed": count,
            }
        except HTTPException:
            pass

    # Legacy fallback for backward-compatible unauthenticated runs
    chunks = load_chunks(UPLOAD_DIR)
    if not chunks:
        raise HTTPException(
            status_code=400,
            detail=f"No supported documents found in {UPLOAD_DIR}. Add PDF, TXT, Markdown, or code files first."
        )
    print(f"Loaded {len(chunks)} chunks. Starting embedding generation...", flush=True)
    count = default_index.build(chunks)
    default_index.save(INDEX_DIR)
    print(f"Embedding generation completed and index persisted ({count} chunks).", flush=True)
    return {
        "status": "indexed",
        "files_directory": str(UPLOAD_DIR),
        "chunks_indexed": count,
    }


@app.post("/query", response_model=QueryResponse)
def query(
    request: QueryRequest,
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> QueryResponse:
    # If user provides authentication, query strictly in their isolated workspace
    active_index = default_index
    active_retriever = default_retriever

    if credentials and credentials.credentials:
        try:
            current_user = get_current_user(credentials)
            user_idx, user_ret = workspace_manager.get_user_workspace(current_user.id)
            active_index = user_idx
            active_retriever = user_ret
        except HTTPException:
            pass

    if not active_index.chunks:
        raise HTTPException(
            status_code=400,
            detail="No documents indexed yet. Add files to data/uploads and call POST /ingest."
        )

    results = active_retriever.retrieve(request.question, top_k=request.top_k)

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
