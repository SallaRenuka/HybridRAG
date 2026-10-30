from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = ROOT_DIR / "data" / "uploads"
INDEX_DIR = ROOT_DIR / "data" / "index"

# Small, CPU-friendly defaults. Models download on first use.
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
SUPPORTED_EXTENSIONS = {
    ".pdf", ".txt", ".md", ".py", ".js", ".ts", ".tsx", ".jsx",
    ".java", ".go", ".rs", ".c", ".h", ".cpp", ".hpp", ".json",
    ".yaml", ".yml", ".toml", ".sh", ".sql", ".html", ".css"
}

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
INDEX_DIR.mkdir(parents=True, exist_ok=True)
