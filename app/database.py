from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Iterator

from app.config import DATABASE_PATH


@dataclass
class User:
    id: int
    email: str
    password_hash: str
    created_at: str
    updated_at: str


@dataclass
class Session:
    token: str
    user_id: int
    created_at: str
    expires_at: str
    is_revoked: bool


@dataclass
class DocumentRecord:
    id: int
    user_id: int
    filename: str
    file_hash: str
    file_size_bytes: int
    chunk_count: int
    created_at: str


@dataclass
class ConversationRecord:
    id: int
    user_id: int
    title: str
    created_at: str
    updated_at: str


@dataclass
class MessageRecord:
    id: int
    conversation_id: int
    user_id: int
    role: str
    content: str
    citations_json: str | None
    created_at: str


class Database:
    def __init__(self, db_path: Path | str = DATABASE_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    @contextmanager
    def get_connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self.get_connection() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                is_revoked INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                filename TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                file_size_bytes INTEGER NOT NULL,
                chunk_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chat_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                citations_json TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
            CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
            CREATE INDEX IF NOT EXISTS idx_documents_user ON documents(user_id);
            CREATE INDEX IF NOT EXISTS idx_chat_conv_user ON chat_conversations(user_id);
            CREATE INDEX IF NOT EXISTS idx_chat_msg_conv ON chat_messages(conversation_id);
            """)

    # ------------------ User Operations ------------------
    def create_user(self, email: str, password_hash: str) -> User:
        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO users (email, password_hash, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (email.lower().strip(), password_hash, now, now),
            )
            user_id = cursor.lastrowid
            return User(id=user_id, email=email.lower().strip(), password_hash=password_hash, created_at=now, updated_at=now)

    def get_user_by_email(self, email: str) -> User | None:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),)).fetchone()
            if row:
                return User(id=row["id"], email=row["email"], password_hash=row["password_hash"], created_at=row["created_at"], updated_at=row["updated_at"])
            return None

    def get_user_by_id(self, user_id: int) -> User | None:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if row:
                return User(id=row["id"], email=row["email"], password_hash=row["password_hash"], created_at=row["created_at"], updated_at=row["updated_at"])
            return None

    # ------------------ Session Operations ------------------
    def create_session(self, token: str, user_id: int, expires_at: str) -> Session:
        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO sessions (token, user_id, created_at, expires_at, is_revoked) VALUES (?, ?, ?, ?, 0)",
                (token, user_id, now, expires_at),
            )
            return Session(token=token, user_id=user_id, created_at=now, expires_at=expires_at, is_revoked=False)

    def get_session(self, token: str) -> Session | None:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE token = ?", (token,)).fetchone()
            if row:
                return Session(
                    token=row["token"],
                    user_id=row["user_id"],
                    created_at=row["created_at"],
                    expires_at=row["expires_at"],
                    is_revoked=bool(row["is_revoked"]),
                )
            return None

    def revoke_session(self, token: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.execute("UPDATE sessions SET is_revoked = 1 WHERE token = ?", (token,))
            return cursor.rowcount > 0

    # ------------------ Document Operations ------------------
    def create_document(
        self,
        user_id: int,
        filename: str,
        file_hash: str,
        file_size_bytes: int,
        chunk_count: int = 0,
    ) -> DocumentRecord:
        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO documents (user_id, filename, file_hash, file_size_bytes, chunk_count, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, filename, file_hash, file_size_bytes, chunk_count, now),
            )
            return DocumentRecord(
                id=cursor.lastrowid,
                user_id=user_id,
                filename=filename,
                file_hash=file_hash,
                file_size_bytes=file_size_bytes,
                chunk_count=chunk_count,
                created_at=now,
            )

    def get_user_documents(self, user_id: int) -> list[DocumentRecord]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM documents WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
            return [
                DocumentRecord(
                    id=row["id"],
                    user_id=row["user_id"],
                    filename=row["filename"],
                    file_hash=row["file_hash"],
                    file_size_bytes=row["file_size_bytes"],
                    chunk_count=row["chunk_count"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]

    def get_user_document_by_id(self, document_id: int, user_id: int) -> DocumentRecord | None:
        """Fetch document strictly enforcing user ownership."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id = ? AND user_id = ?", (document_id, user_id)).fetchone()
            if row:
                return DocumentRecord(
                    id=row["id"],
                    user_id=row["user_id"],
                    filename=row["filename"],
                    file_hash=row["file_hash"],
                    file_size_bytes=row["file_size_bytes"],
                    chunk_count=row["chunk_count"],
                    created_at=row["created_at"],
                )
            return None

    def delete_user_document(self, document_id: int, user_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.execute("DELETE FROM documents WHERE id = ? AND user_id = ?", (document_id, user_id))
            return cursor.rowcount > 0

    # ------------------ Chat Conversation Operations ------------------
    def create_conversation(self, user_id: int, title: str) -> ConversationRecord:
        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO chat_conversations (user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (user_id, title.strip(), now, now),
            )
            return ConversationRecord(id=cursor.lastrowid, user_id=user_id, title=title.strip(), created_at=now, updated_at=now)

    def get_user_conversations(self, user_id: int) -> list[ConversationRecord]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM chat_conversations WHERE user_id = ? ORDER BY updated_at DESC", (user_id,)).fetchall()
            return [
                ConversationRecord(
                    id=row["id"],
                    user_id=row["user_id"],
                    title=row["title"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in rows
            ]

    def get_conversation_by_id(self, conversation_id: int, user_id: int) -> ConversationRecord | None:
        """Fetch conversation strictly enforcing user ownership."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM chat_conversations WHERE id = ? AND user_id = ?", (conversation_id, user_id)).fetchone()
            if row:
                return ConversationRecord(
                    id=row["id"],
                    user_id=row["user_id"],
                    title=row["title"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            return None

    def add_chat_message(
        self,
        conversation_id: int,
        user_id: int,
        role: str,
        content: str,
        citations_json: str | None = None,
    ) -> MessageRecord:
        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO chat_messages (conversation_id, user_id, role, content, citations_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (conversation_id, user_id, role, content, citations_json, now),
            )
            conn.execute("UPDATE chat_conversations SET updated_at = ? WHERE id = ?", (now, conversation_id))
            return MessageRecord(
                id=cursor.lastrowid,
                conversation_id=conversation_id,
                user_id=user_id,
                role=role,
                content=content,
                citations_json=citations_json,
                created_at=now,
            )

    def get_messages_for_conversation(self, conversation_id: int, user_id: int) -> list[MessageRecord]:
        """Fetch all messages for conversation strictly verifying user ownership."""
        conv = self.get_conversation_by_id(conversation_id, user_id)
        if not conv:
            return []
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM chat_messages WHERE conversation_id = ? AND user_id = ? ORDER BY id ASC",
                (conversation_id, user_id),
            ).fetchall()
            return [
                MessageRecord(
                    id=row["id"],
                    conversation_id=row["conversation_id"],
                    user_id=row["user_id"],
                    role=row["role"],
                    content=row["content"],
                    citations_json=row["citations_json"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]
