# HybridRAG Engine

A local-first RAG starter project for PDF and text/code files. It combines:
- PDF/text/code ingestion and overlapping chunking
- Sentence-Transformer embeddings + FAISS vector search
- BM25 keyword search
- Reciprocal Rank Fusion (RRF) to combine rankings
- Optional Cross-Encoder reranking
- FastAPI endpoints with source citations
- Streamlit UI
- Pytest tests and Docker support

## 1. Requirements
- Python 3.11 or 3.12 recommended
- macOS, Windows, or Linux
- Internet access on first run to download Hugging Face models

## 2. Setup on macOS (PyCharm Terminal)

Create/open this project in PyCharm, then run:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If FAISS fails to install, check that the selected Python version is 3.11/3.12 and share the complete error.

## 3. Add documents
Put `.pdf`, `.txt`, `.md`, `.py`, `.js`, `.ts`, `.java`, `.go`, `.rs`, `.json`, `.yaml`, or `.yml` files in `data/uploads/`.

Then start the API and call the `/ingest` endpoint, or use the UI's **Re-index documents** button.

## 4. Run the API
```bash
uvicorn app.main:app --reload
```
Open `http://127.0.0.1:8000/docs` to try the API.

## 5. Run the UI (in a second terminal)
Activate the same virtual environment, then:
```bash
streamlit run ui.py
```

## 6. Run tests
```bash
pytest -q
```

## API endpoints
- `GET /health`
- `POST /ingest` — indexes files found in `data/uploads/`
- `POST /query` — JSON body: `{"question": "How does authentication work?", "top_k": 3}`

## Notes
- The first embedding/re-ranker model load downloads model files and may take a while.
- Default models run locally. The starter does not call a hosted LLM yet; `/query` returns an extractive, source-grounded response from retrieved chunks. This makes retrieval testable before adding Ollama or a hosted generation API.
- FAISS and BM25 indexes are rebuilt in memory when the API starts. For a production version, persist indexes and metadata, add incremental updates, file-size limits, authentication, and stronger prompt-injection defenses.
- Retrieval latency depends on your Mac, number of chunks, and whether models are already loaded.
