from dataclasses import dataclass, asdict
from pathlib import Path
import re
from typing import Iterable

from pypdf import PdfReader

from app.config import UPLOAD_DIR, SUPPORTED_EXTENSIONS


@dataclass
class Chunk:
    chunk_id: str
    text: str
    source: str
    page: int | None = None

    def to_dict(self):
        return asdict(self)


def read_file(path: Path) -> list[tuple[str, int | None]]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        pages = []

        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            text = text.replace("\x00", " ")
            text = re.sub(r"[ \t]+", " ", text)
            text = re.sub(r" *\n *", "\n", text)
            text = re.sub(r"\n{3,}", "\n\n", text)
            pages.append((text.strip(), page_num))

        return pages

    if suffix in SUPPORTED_EXTENSIONS:
        try:
            return [(path.read_text(encoding="utf-8", errors="replace"), None)]
        except OSError:
            return []

    return []


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")

    # Remove invalid Unicode surrogate characters from extracted PDF text
    text = text.encode("utf-8", errors="replace").decode("utf-8")

    # Normalize whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def chunk_text(text: str, chunk_size: int = 1800, overlap: int = 250) -> list[str]:
    """Character-based starter chunker with paragraph/sentence-friendly boundaries.

    These are character counts, not token counts. It favors paragraph/newline/sentence
    boundaries where possible and includes overlap to preserve nearby context.
    """
    text = clean_text(text)
    if not text:
        return []
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("Require chunk_size > overlap >= 0")
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        if end < n:
            floor = start + int(chunk_size * 0.65)
            candidates = [
                text.rfind("\n\n", floor, end),
                text.rfind("\n", floor, end),
                text.rfind(". ", floor, end),
                text.rfind("; ", floor, end),
                text.rfind(" ", floor, end),
            ]
            boundary = max(candidates)
            if boundary > start:
                end = boundary + (2 if text[boundary:boundary+2] in {"\n\n", ". "} else 1)
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks


def load_chunks(directory: Path = UPLOAD_DIR) -> list[Chunk]:
    all_chunks: list[Chunk] = []
    if not directory.exists():
        return all_chunks
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        try:
            pages = read_file(path)
        except Exception as exc:
            print(f"Skipping {path.name}: {exc}")
            continue
        relative_source = str(path.relative_to(directory))
        for text, page in pages:
            for i, chunk in enumerate(chunk_text(text)):
                all_chunks.append(
                    Chunk(
                        chunk_id=f"{relative_source}::p{page or 0}::c{i}",
                        text=chunk,
                        source=relative_source,
                        page=page,
                    )
                )
    return all_chunks
