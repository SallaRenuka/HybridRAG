from __future__ import annotations

import hashlib
import threading
from pathlib import Path
from typing import Dict, Tuple

from app.config import (
    UPLOAD_DIR,
    INDEX_DIR,
    get_user_upload_dir,
    get_user_index_dir,
)
from app.ingest import load_chunks
from app.retriever import Retriever
from app.search_index import HybridIndex


def compute_file_sha256(file_bytes: bytes) -> str:
    """Compute SHA-256 cryptographic checksum of file content."""
    hasher = hashlib.sha256()
    hasher.update(file_bytes)
    return hasher.hexdigest()


class WorkspaceManager:
    """Manages strictly isolated document stores and FAISS/BM25 indexes per user."""

    def __init__(self):
        self._user_workspaces: Dict[int, Tuple[HybridIndex, Retriever]] = {}
        self._lock = threading.Lock()
        # Default workspace for legacy/unauthenticated tests
        self._default_index = HybridIndex()
        self._default_retriever = Retriever(index=self._default_index, use_reranker=True)
        if INDEX_DIR.exists():
            self._default_index.load(INDEX_DIR)

    def get_default_workspace(self) -> Tuple[HybridIndex, Retriever]:
        return self._default_index, self._default_retriever

    def get_user_workspace(self, user_id: int) -> Tuple[HybridIndex, Retriever]:
        """Fetch or initialize the isolated HybridIndex and Retriever for a specific user."""
        with self._lock:
            if user_id not in self._user_workspaces:
                user_index = HybridIndex()
                user_index_dir = get_user_index_dir(user_id)
                if user_index_dir.exists():
                    user_index.load(user_index_dir)
                user_retriever = Retriever(index=user_index, use_reranker=True)
                self._user_workspaces[user_id] = (user_index, user_retriever)
            return self._user_workspaces[user_id]

    def ingest_user_documents(self, user_id: int) -> int:
        """Extract and index documents strictly from the user's isolated upload directory."""
        upload_dir = get_user_upload_dir(user_id)
        index_dir = get_user_index_dir(user_id)
        chunks = load_chunks(upload_dir)
        if not chunks:
            return 0

        user_index, _ = self.get_user_workspace(user_id)
        count = user_index.build(chunks)
        user_index.save(index_dir)
        return count

    def remove_user_document_file_and_reindex(self, user_id: int, filename: str) -> int:
        """Safely delete uploaded file from user's isolated directory and rebuild index."""
        upload_dir = get_user_upload_dir(user_id)
        index_dir = get_user_index_dir(user_id)
        file_path = upload_dir / filename
        if file_path.exists():
            file_path.unlink()

        chunks = load_chunks(upload_dir)
        user_index, _ = self.get_user_workspace(user_id)
        if not chunks:
            user_index.chunks = []
            user_index.faiss_index = None
            user_index.bm25 = None
            for meta_name in ("faiss.index", "metadata.json", "faiss.index.tmp", "metadata.json.tmp"):
                p = index_dir / meta_name
                if p.exists():
                    p.unlink(missing_ok=True)
            return 0

        count = user_index.build(chunks)
        user_index.save(index_dir)
        return count


workspace_manager = WorkspaceManager()
