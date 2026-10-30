import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
INDEX_DIR = DATA_DIR / "index"
USERS_DIR = DATA_DIR / "users"
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(DATA_DIR / "hybridrag.db")))
SECRET_KEY = os.getenv("SECRET_KEY", "hybridrag-dev-secret-key-change-in-production")
TOKEN_EXPIRATION_HOURS = int(os.getenv("TOKEN_EXPIRATION_HOURS", "24"))

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
USERS_DIR.mkdir(parents=True, exist_ok=True)


def get_user_upload_dir(user_id: int) -> Path:
    user_upload = USERS_DIR / str(user_id) / "uploads"
    user_upload.mkdir(parents=True, exist_ok=True)
    return user_upload


def get_user_index_dir(user_id: int) -> Path:
    user_index = USERS_DIR / str(user_id) / "index"
    user_index.mkdir(parents=True, exist_ok=True)
    return user_index
