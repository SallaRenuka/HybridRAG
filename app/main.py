from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any

from fastapi import Depends, FastAPI, File, HTTPException, Security, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
import requests

from app.answer_generator import dynamic_answer_generator
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
from app.query_understanding import query_understanding_engine, QueryIntent
from app.retriever import Retriever
from app.search_index import HybridIndex, tokenize
from app.workspace import workspace_manager, compute_file_sha256

INSUFFICIENT_INFO_MESSAGE = "The provided documents do not contain sufficient information to answer this question."

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


def sync_user_document_chunk_counts(user_id: int) -> dict[str, int]:
    """Accurately count chunks per document from the user's index and synchronize the database."""
    user_idx, _ = workspace_manager.get_user_workspace(user_id)
    counts_by_source: dict[str, int] = {}
    for c in user_idx.chunks:
        counts_by_source[c.source] = counts_by_source.get(c.source, 0) + 1

    with db.get_connection() as conn:
        docs = conn.execute("SELECT id, filename FROM documents WHERE user_id = ?", (user_id,)).fetchall()
        for doc_id, fname in docs:
            true_count = counts_by_source.get(fname, 0)
            conn.execute("UPDATE documents SET chunk_count = ? WHERE id = ?", (true_count, doc_id))

    return counts_by_source


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Automatically load persisted index on startup if available
    try:
        if default_index.load(INDEX_DIR):
            print(f"Loaded existing index with {len(default_index.chunks)} chunks from {INDEX_DIR}", flush=True)
    except Exception as exc:
        print(f"Failed to load existing index on startup: {exc}", flush=True)

    # Sync chunk counts for existing user documents from their index metadata
    try:
        with db.get_connection() as conn:
            user_ids = [r[0] for r in conn.execute("SELECT DISTINCT user_id FROM documents").fetchall()]
        for u_id in user_ids:
            sync_user_document_chunk_counts(u_id)
    except Exception as exc:
        print(f"Document chunk count sync on startup warning: {exc}", flush=True)
    yield


app = FastAPI(
    title="HybridRAG Enterprise Engine",
    version="1.0.0",
    description="Enterprise-grade Document Intelligence and Question Answering Platform with User Isolation and Authentication",
    lifespan=lifespan,
)

# Enable CORS for local development and modern frontend applications
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------ Request & Response Schemas ------------------
class QueryRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=10)


class Citation(BaseModel):
    id: int
    source: str
    chunk_id: str
    page: int | None = None
    text: str


class QueryResponse(BaseModel):
    answer: str
    generation_type: str = "llm"  # "llm" | "extractive_summary" | "insufficient_information"
    citations: list[Citation]
    note: str


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    document_id: int | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class SearchResultItem(BaseModel):
    chunk_id: str
    source: str
    page: int | None = None
    text: str
    rrf_score: float
    rerank_score: float | None = None
    highlights: list[str] = []


class SearchResponse(BaseModel):
    query: str
    total_results: int
    results: list[SearchResultItem]


class CreateConversationRequest(BaseModel):
    title: str = Field(default="New Conversation", min_length=1, max_length=255)


class SendMessageRequest(BaseModel):
    message: str = Field(min_length=2, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=10)


# ------------------ Claim & Citation Verification Helpers ------------------
DEFINITIONAL_PATTERNS = [
    re.compile(r"\b(?:is|are)\s+(?:the\s+)?(?:science|art|field|study|discipline|branch|process|technique|method|system|framework|approach|technology|capability|ability)\b", re.IGNORECASE),
    re.compile(r"\b(?:is|are)\s+defined\s+as\b", re.IGNORECASE),
    re.compile(r"\b(?:refers\s+to|means|consists\s+of|is\s+about)\b", re.IGNORECASE),
    re.compile(r"\bcan\s+be\s+(?:categorized|classified|divided|grouped|split)\s+into\b", re.IGNORECASE),
    re.compile(r"\bthere\s+are\s+(?:several|four|three|two|many|broad|major)\s+(?:categories|types|classes|kinds)\b", re.IGNORECASE),
]

DISQUALIFY_PATTERNS = [
    re.compile(r"^(?:if you already know|in this chapter|solutions to the|download(?:ing)? a copy of wikipedia|stepping back|appendix|figure \d|table \d|jupyter notebook)", re.IGNORECASE),
    re.compile(r"\?$", re.IGNORECASE),
    re.compile(r"^(?:what is|how to|why use|types of)\b", re.IGNORECASE),
]


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

    # Evaluate against single-sentence and rolling 2-sentence windows to support multi-clause synthesis
    windows = list(chunk_sentences)
    for i in range(len(chunk_sentences) - 1):
        windows.append(f"{chunk_sentences[i]} {chunk_sentences[i+1]}")

    best_overlap = 0.0
    best_matching_window = ""

    for w in windows:
        w_tokens = set(tokenize(w))
        overlap = len(claim_tokens & w_tokens) / len(claim_tokens)
        if overlap > best_overlap:
            best_overlap = overlap
            best_matching_window = w

    # Also compute full chunk token coverage
    chunk_all_tokens = set(tokenize(chunk_text))
    full_chunk_overlap = len(claim_tokens & chunk_all_tokens) / len(claim_tokens)

    effective_overlap = max(best_overlap, full_chunk_overlap * 0.9)
    if effective_overlap < min_overlap:
        return False

    claim_has_neg = bool(set(tokenize(claim_sentence)) & NEGATION_WORDS)
    match_has_neg = bool(set(tokenize(best_matching_window or chunk_text)) & NEGATION_WORDS)
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


COMMON_ABBREVIATIONS = ["vs.", "e.g.", "i.e.", "al.", "etc.", "fig.", "ref.", "dr.", "mr.", "ms."]


def split_into_statements(text: str) -> list[str]:
    """Split text into sentences or Markdown list/table items while protecting abbreviations."""
    protected = text
    for abbr in COMMON_ABBREVIATIONS:
        protected = re.sub(r"\b" + re.escape(abbr), abbr.replace(".", "@@DOT@@"), protected, flags=re.IGNORECASE)

    statements = []
    lines = protected.split("\n")
    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue
        # Table rows, markdown list items, or headers
        if line_str.startswith("|") or line_str.startswith("- ") or line_str.startswith("* ") or re.match(r"^\d+\.\s+", line_str) or line_str.startswith("#"):
            statements.append(line_str)
        else:
            sents = re.split(r"(?<=[.!?])\s+", line_str)
            for s in sents:
                if s.strip():
                    statements.append(s.strip())

    return [s.replace("@@DOT@@", ".").strip() for s in statements if s.strip()]


def process_answer_and_citations(
    raw_answer: str,
    citation_map: dict[int, Citation],
) -> tuple[str, list[Citation]]:
    """Validate every statement in the response. Remove unsupported claims and invalid citation IDs."""
    if (
        not raw_answer
        or INSUFFICIENT_INFO_MESSAGE.lower() in raw_answer.lower()
        or "could not find sufficient information" in raw_answer.lower()
        or "do not contain sufficient information" in raw_answer.lower()
    ):
        return INSUFFICIENT_INFO_MESSAGE, []

    statements = split_into_statements(raw_answer)
    if not statements:
        return INSUFFICIENT_INFO_MESSAGE, []

    verified_statements: list[str] = []
    verified_citation_ids: set[int] = set()

    for stmt in statements:
        # Preserve Markdown table formatting dividers, rows, or headings
        if re.match(r"^\|[\s\-:|]+\|$", stmt) or stmt.startswith("#"):
            cited_in_stmt = [int(m) for m in re.findall(r"\[(\d+)\]", stmt) if int(m) in citation_map]
            verified_citation_ids.update(cited_in_stmt)
            verified_statements.append(stmt)
            continue

        if stmt.startswith("|") and stmt.endswith("|"):
            cited_in_stmt = [int(m) for m in re.findall(r"\[(\d+)\]", stmt) if int(m) in citation_map]
            verified_citation_ids.update(cited_in_stmt)
            verified_statements.append(stmt)
            continue

        cited_indices = [int(m) for m in re.findall(r"\[(\d+)\]", stmt)]
        claim_tokens = extract_claim_tokens(stmt)
        is_factual = len(claim_tokens) >= 2

        sentence_verified_ids = []

        if cited_indices:
            # Check explicitly cited chunks
            valid_indices = [cid for cid in cited_indices if cid in citation_map]
            for cid in valid_indices:
                target_chunk = citation_map[cid]
                if check_sentence_support_and_consistency(stmt, target_chunk.text):
                    sentence_verified_ids.append(cid)
        else:
            # Check if this factual claim is strictly supported by any candidate chunk
            if is_factual:
                for cid, target_chunk in citation_map.items():
                    if check_sentence_support_and_consistency(stmt, target_chunk.text, min_overlap=0.38):
                        sentence_verified_ids.append(cid)
                        break

        # Discard factual claims that lack verified source support
        if is_factual and not sentence_verified_ids:
            continue

        # Keep non-factual connective phrases only if we already have verified statements
        if not is_factual and not sentence_verified_ids:
            if verified_statements:
                verified_statements.append(stmt)
            continue

        cleaned_text = re.sub(r"\s*\[\d+\]", "", stmt).strip()
        tags = "".join(f"[{cid}]" for cid in sorted(set(sentence_verified_ids)))
        if cleaned_text.endswith((".", "!", "?")):
            cleaned_sent = f"{cleaned_text[:-1].rstrip()} {tags}{cleaned_text[-1]}"
        else:
            cleaned_sent = f"{cleaned_text.rstrip()} {tags}"

        verified_statements.append(cleaned_sent)
        verified_citation_ids.update(sentence_verified_ids)

    if not verified_citation_ids:
        # If statements contain table rows, verify if candidate chunks support the table content
        has_table_rows = False
        for stmt in verified_statements:
            if stmt.startswith("|") and stmt.endswith("|") and not re.match(r"^\|[\s\-:|]+\|$", stmt):
                has_table_rows = True
                row_tokens = extract_claim_tokens(stmt)
                for cid, target_chunk in citation_map.items():
                    chunk_tokens = set(tokenize(target_chunk.text))
                    if row_tokens and len(row_tokens & chunk_tokens) >= 2:
                        verified_citation_ids.add(cid)
                        break
        if not has_table_rows or not verified_citation_ids:
            return INSUFFICIENT_INFO_MESSAGE, []

    # Join with newlines if containing Markdown blocks or list items, else spaces
    has_blocks = any("\n" in s or s.startswith("|") or s.startswith("#") or s.startswith("-") or s.startswith("*") for s in verified_statements)
    final_answer = "\n\n".join(verified_statements) if has_blocks else " ".join(verified_statements)
    final_citations = [citation_map[cid] for cid in sorted(verified_citation_ids)]
    return final_answer, final_citations


def generate_extractive_summary(
    results: list[dict],
    citation_map: dict[int, Citation],
    query: str = "",
    user_id: int | None = None,
) -> tuple[str, list[Citation]]:
    """Generate dynamic formatted answers grounded in verified source documents."""
    return dynamic_answer_generator.generate(
        query=query,
        results=results,
        citation_map=citation_map,
        user_id=user_id,
    )


def clean_llm_response(raw: str) -> str:
    """Normalize LLM output to clean, professional Markdown.

    Fixes common artifacts produced by smaller local models:
    - Literal ``\\n`` / ``\\t`` escape sequences → real whitespace
    - Double-escaped backslashes outside code blocks → single backslash
    - Broken list numbering such as ``2 [1].`` → ``2.``
    - Trailing whitespace on every line
    - More than two consecutive blank lines collapsed to two
    """
    if not raw:
        return raw

    # --- 1. Preserve fenced code blocks verbatim ---
    code_blocks: list[str] = []
    placeholder_tpl = "\x00CODE{}\x00"

    def _stash_code(m: re.Match) -> str:
        code_blocks.append(m.group(0))
        return placeholder_tpl.format(len(code_blocks) - 1)

    text = re.sub(r"```[\s\S]*?```", _stash_code, raw)

    # --- 2. Fix literal escape sequences ---
    text = text.replace("\\n", "\n")
    text = text.replace("\\t", "\t")
    # Double-backslash outside code → single backslash
    text = text.replace("\\\\", "\\")

    # --- 3. Fix broken numbered list items like "2 [1]." or "3. [2]."
    # Pattern: digit(s), optional period, space, citation tag(s), optional period
    text = re.sub(r"(\d+)\.?\s+(\[\d+\])+\.?", lambda m: m.group(1) + ".", text)

    # --- 4. Strip trailing whitespace per line ---
    lines = [line.rstrip() for line in text.splitlines()]

    # --- 5. Collapse more than 2 consecutive blank lines ---
    cleaned_lines: list[str] = []
    blank_run = 0
    for line in lines:
        if line == "":
            blank_run += 1
            if blank_run <= 2:
                cleaned_lines.append(line)
        else:
            blank_run = 0
            cleaned_lines.append(line)

    text = "\n".join(cleaned_lines).strip()

    # --- 6. Restore code blocks ---
    for i, block in enumerate(code_blocks):
        text = text.replace(placeholder_tpl.format(i), block)

    return text


_FORMATTING_SYSTEM_PROMPT = """\
You are a professional AI assistant that answers questions strictly from provided document context.

FORMATTING RULES:
- Use clean Markdown formatting: headings (##, ###), bullet lists (-), numbered lists, bold (**text**), code blocks (```).
- Do NOT start answers with "Answer:" or repeat the question.
- Do NOT output raw \\n literals.

CITATION RULES (critical — obey strictly):
- Every single factual claim, sentence, bullet point, and list item MUST end with one or more citation tags in brackets, e.g. [1] or [1][2].
- Use ONLY the citation IDs provided in the Document Context below (e.g. [1], [2], [3]).
- Do NOT invent citation IDs. Do NOT omit citations on bullet points or lists.
- If the context does not contain sufficient information, respond with EXACTLY:
  "The provided documents do not contain sufficient information to answer this question."
"""


def call_ollama(prompt: str, model_name: str = "llama3.2:3b", timeout: int = 120) -> str:
    """Call local Ollama generation API."""
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": model_name, "prompt": prompt, "stream": False},
        timeout=timeout,
    )
    response.raise_for_status()
    raw = response.json()["response"].strip()
    return clean_llm_response(raw)


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


@app.get("/documents/{document_id}/file")
def get_document_file(
    document_id: int,
    current_user: User = Depends(get_current_user),
):
    """Serve the raw document file with inline disposition for in-browser PDF viewing and page jumping."""
    doc = db.get_user_document_by_id(document_id, current_user.id)
    if not doc:
        with db.get_connection() as conn:
            exists = conn.execute("SELECT id, user_id FROM documents WHERE id = ?", (document_id,)).fetchone()
            if exists:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: You do not have permission to view documents belonging to another user.",
                )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    user_upload_dir = get_user_upload_dir(current_user.id)
    file_path = user_upload_dir / doc.filename
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document file not found on disk.")

    media_type = "application/pdf" if doc.filename.lower().endswith(".pdf") else "application/octet-stream"
    return FileResponse(
        path=str(file_path),
        filename=doc.filename,
        media_type=media_type,
        content_disposition_type="inline",
    )


@app.delete("/documents/{document_id}")
def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Safely delete document from database, disk, and rebuild the user's isolated FAISS/BM25 index."""
    doc = db.get_user_document_by_id(document_id, current_user.id)
    if not doc:
        with db.get_connection() as conn:
            exists = conn.execute("SELECT id, user_id FROM documents WHERE id = ?", (document_id,)).fetchone()
            if exists:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: You do not have permission to delete this document.",
                )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    # 1. Remove file and reindex remaining documents strictly within user's workspace
    workspace_manager.remove_user_document_file_and_reindex(current_user.id, doc.filename)

    # 2. Delete database record
    db.delete_user_document(document_id, current_user.id)

    # 3. Synchronize chunk counts for remaining documents
    sync_user_document_chunk_counts(current_user.id)

    return {
        "status": "deleted",
        "document_id": document_id,
        "filename": doc.filename,
        "message": f"Document '{doc.filename}' safely removed and index updated.",
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

    # Automatically index user's isolated workspace
    warning_msg = None
    try:
        workspace_manager.ingest_user_documents(current_user.id)
        counts = sync_user_document_chunk_counts(current_user.id)
        doc_record.chunk_count = counts.get(safe_filename, 0)
        if doc_record.chunk_count == 0:
            warning_msg = (
                "No extractable text was found in this document. "
                "If this is a scanned PDF or contains only image-based pages, text extraction cannot index its contents."
            )
    except Exception as exc:
        print(f"Auto-indexing warning: {exc}", flush=True)

    resp = {
        "status": "uploaded",
        "document_id": doc_record.id,
        "filename": doc_record.filename,
        "file_size_bytes": doc_record.file_size_bytes,
        "chunk_count": doc_record.chunk_count,
    }
    if warning_msg:
        resp["warning"] = warning_msg
    return resp


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


@app.delete("/chat/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Delete a conversation thread strictly enforcing user ownership."""
    conv = db.get_conversation_by_id(conversation_id, current_user.id)
    if not conv:
        with db.get_connection() as conn:
            exists = conn.execute("SELECT id, user_id FROM chat_conversations WHERE id = ?", (conversation_id,)).fetchone()
            if exists:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: You do not have permission to delete this conversation.",
                )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    db.delete_conversation(conversation_id, current_user.id)
    return {"status": "deleted", "conversation_id": conversation_id}


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

    # Fetch prior conversation messages for contextual follow-up questions
    prior_messages = db.get_messages_for_conversation(conversation_id, current_user.id)
    history_context = ""
    if len(prior_messages) > 1:
        history_lines = [f"{m.role.capitalize()}: {m.content}" for m in prior_messages[-5:-1]]
        history_context = "Conversation History (for context):\n" + "\n".join(history_lines) + "\n\n"

    # Query strictly within current user's isolated workspace
    user_index, user_retriever = workspace_manager.get_user_workspace(current_user.id)
    if not user_index.chunks:
        answer = INSUFFICIENT_INFO_MESSAGE
        generation_type = "insufficient_information"
        citations = []
        note = "No documents indexed in your workspace. Please upload and index documents first."
    else:
        results = user_retriever.retrieve(request.message, top_k=request.top_k)
        formatted_context, citation_map = format_context_and_citation_map(results)
        norm_q = query_understanding_engine.analyze(request.message)

        is_structured_employee_query = (
            bool(norm_q.entity_ids)
            or norm_q.intent in [
                QueryIntent.ENTITY_PROFILE,
                QueryIntent.ENTITY_FIELD,
                QueryIntent.COMPARISON,
                QueryIntent.RANKING,
                QueryIntent.STATISTICS,
            ]
        )

        if is_structured_employee_query:
            answer, citations = generate_extractive_summary(
                results, citation_map, query=request.message, user_id=current_user.id
            )
            generation_type = "structured_record" if answer != INSUFFICIENT_INFO_MESSAGE else "insufficient_information"
            note = "Authoritative structured record answer verified against source document."
        elif not results:
            answer = INSUFFICIENT_INFO_MESSAGE
            generation_type = "insufficient_information"
            citations = []
            note = "No relevant chunks passed retrieval threshold."
        else:
            format_hint = f"EXPECTED FORMAT: {norm_q.target_format.value}"
            prompt = f"""{_FORMATTING_SYSTEM_PROMPT}

{format_hint}

Document Context:
{formatted_context}

{history_context}Current Question: {request.message}

Answer:"""
            try:
                raw_ans = call_ollama(prompt)
                answer, citations = process_answer_and_citations(raw_ans, citation_map)
                if answer == INSUFFICIENT_INFO_MESSAGE:
                    answer, citations = generate_extractive_summary(results, citation_map, query=request.message, user_id=current_user.id)
                generation_type = "llm" if answer != INSUFFICIENT_INFO_MESSAGE else "insufficient_information"
                note = "Answer synthesized from verified document passages."
            except requests.RequestException:
                # Extractive fallback: do NOT present as LLM text, clearly mark as direct source excerpts
                answer, citations = generate_extractive_summary(results, citation_map, query=request.message, user_id=current_user.id)
                generation_type = "extractive_summary" if answer != INSUFFICIENT_INFO_MESSAGE else "insufficient_information"
                note = "LLM offline. Showing verified document excerpts directly from source passages."

    # Record assistant message in DB with citations
    citations_data = [c.model_dump() for c in citations]
    db.add_chat_message(
        conversation_id=conversation_id,
        user_id=current_user.id,
        role="assistant",
        content=answer,
        citations_json=json.dumps(citations_data),
    )

    return QueryResponse(answer=answer, generation_type=generation_type, citations=citations, note=note)


# ------------------ Analytics & Enterprise Search Endpoints ------------------
@app.get("/dashboard/stats")
def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Provide real, aggregate metrics for the authenticated user's workspace."""
    stats = db.get_user_stats(current_user.id)
    recent_docs = db.get_user_documents(current_user.id)[:5]
    recent_convs = db.get_user_conversations(current_user.id)[:5]

    user_upload_dir = get_user_upload_dir(current_user.id)
    total_pages = 0
    if user_upload_dir.exists():
        from pypdf import PdfReader
        for pdf_path in user_upload_dir.glob("*.pdf"):
            try:
                reader = PdfReader(str(pdf_path))
                total_pages += len(reader.pages)
            except Exception:
                pass

    from app.document_analyzer import document_analyzer
    records = document_analyzer.get_all_records(user_upload_dir) if user_upload_dir.exists() else []
    dept_counts: dict[str, int] = {}
    exp_ranges = {"0-2 yrs": 0, "3-5 yrs": 0, "6-10 yrs": 0, "11+ yrs": 0}

    for r in records:
        dept = r.data.get("Department")
        if dept:
            dept_counts[dept] = dept_counts.get(dept, 0) + 1
        exp = r.data.get("Experience")
        if isinstance(exp, (int, float)):
            if exp <= 2:
                exp_ranges["0-2 yrs"] += 1
            elif exp <= 5:
                exp_ranges["3-5 yrs"] += 1
            elif exp <= 10:
                exp_ranges["6-10 yrs"] += 1
            else:
                exp_ranges["11+ yrs"] += 1

    return {
        **stats,
        "total_pages_processed": total_pages,
        "structured_records_count": len(records),
        "department_distribution": dept_counts,
        "experience_distribution": exp_ranges,
        "recent_documents": [
            {
                "id": d.id,
                "filename": d.filename,
                "file_size_bytes": d.file_size_bytes,
                "chunk_count": d.chunk_count,
                "created_at": d.created_at,
            }
            for d in recent_docs
        ],
        "recent_conversations": [
            {
                "id": c.id,
                "title": c.title,
                "created_at": c.created_at,
                "updated_at": c.updated_at,
            }
            for c in recent_convs
        ],
    }


@app.post("/search", response_model=SearchResponse)
def enterprise_search(
    request: SearchRequest,
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> SearchResponse:
    """Dedicated enterprise search across documents with RRF + neural ranking and keyword highlighting."""
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
        return SearchResponse(query=request.query, total_results=0, results=[])

    raw_results = active_retriever.retrieve(request.query, top_k=request.top_k)
    query_tokens = set(tokenize(request.query))

    formatted_items = []
    for item in raw_results:
        chunk = item["chunk"]
        text_tokens = tokenize(chunk.text)
        matched_tokens = sorted(list(query_tokens & set(text_tokens)))

        formatted_items.append(
            SearchResultItem(
                chunk_id=chunk.chunk_id,
                source=chunk.source,
                page=chunk.page,
                text=chunk.text,
                rrf_score=float(item.get("rrf_score", 0.0)),
                rerank_score=float(item["rerank_score"]) if item.get("rerank_score") is not None else None,
                highlights=matched_tokens,
            )
        )

    return SearchResponse(
        query=request.query,
        total_results=len(formatted_items),
        results=formatted_items,
    )


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
            sync_user_document_chunk_counts(current_user.id)
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
    current_user_id = None

    if credentials and credentials.credentials:
        try:
            current_user = get_current_user(credentials)
            user_idx, user_ret = workspace_manager.get_user_workspace(current_user.id)
            active_index = user_idx
            active_retriever = user_ret
            current_user_id = current_user.id
        except HTTPException:
            pass

    if not active_index.chunks:
        raise HTTPException(
            status_code=400,
            detail="No documents indexed yet. Add files to data/uploads and call POST /ingest."
        )

    results = active_retriever.retrieve(request.question, top_k=request.top_k)
    norm_q = query_understanding_engine.analyze(request.question)
    formatted_context, citation_map = format_context_and_citation_map(results) if results else ("", {})

    is_structured_employee_query = (
        bool(norm_q.entity_ids)
        or norm_q.intent in [
            QueryIntent.ENTITY_PROFILE,
            QueryIntent.ENTITY_FIELD,
            QueryIntent.COMPARISON,
            QueryIntent.RANKING,
            QueryIntent.STATISTICS,
        ]
    )

    if is_structured_employee_query:
        answer, citations = generate_extractive_summary(
            results, citation_map, query=request.question, user_id=current_user_id
        )
        generation_type = "structured_record" if answer != INSUFFICIENT_INFO_MESSAGE else "insufficient_information"
        note = "Authoritative structured record answer verified against source document."
        return QueryResponse(
            answer=answer,
            generation_type=generation_type,
            citations=citations,
            note=note,
        )

    if not results:
        return QueryResponse(
            answer=INSUFFICIENT_INFO_MESSAGE,
            generation_type="insufficient_information",
            citations=[],
            note="No relevant chunks passed the retrieval and relevance filters."
        )

    format_hint = f"EXPECTED FORMAT: {norm_q.target_format.value}"

    prompt = f"""{_FORMATTING_SYSTEM_PROMPT}

{format_hint}

Document Context:
{formatted_context}

Question: {request.question}

Answer:"""

    try:
        raw_answer = call_ollama(prompt)
        answer, citations = process_answer_and_citations(raw_answer, citation_map)
        if answer == INSUFFICIENT_INFO_MESSAGE:
            answer, citations = generate_extractive_summary(results, citation_map, query=request.question, user_id=current_user_id)
        generation_type = "llm" if answer != INSUFFICIENT_INFO_MESSAGE else "insufficient_information"
        note = "Answer synthesized from verified document passages."

    except requests.RequestException as exc:
        print(f"Ollama offline: {exc}", flush=True)
        answer, citations = generate_extractive_summary(results, citation_map, query=request.question, user_id=current_user_id)
        generation_type = "extractive_summary" if answer != INSUFFICIENT_INFO_MESSAGE else "insufficient_information"
        note = "Document retrieval succeeded; LLM offline. Showing direct verified source excerpts."

    return QueryResponse(
        answer=answer,
        generation_type=generation_type,
        citations=citations,
        note=note,
    )
