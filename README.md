🚀 HybridRAG – AI-Powered Document Intelligence Platform

HybridRAG is an intelligent document search and question-answering platform built using Retrieval-Augmented Generation (RAG). It combines semantic search, keyword-based retrieval, document analysis, and AI-powered answer generation to help users extract meaningful insights from multiple documents.

⸻

✨ Key Features

* 📄 Multi-Format Document Ingestion – Process PDF, text, Markdown, and supported code files.
* 🔍 Hybrid Search – Combines FAISS vector search and BM25 keyword retrieval.
* 🧠 Semantic Search – Understands the meaning and context of user queries.
* ⚡ Reciprocal Rank Fusion (RRF) – Combines results from multiple retrieval techniques.
* 🎯 Cross-Encoder Reranking – Improves the relevance of retrieved results.
* 📊 Document Intelligence – Extracts information and insights from uploaded documents.
* 💬 AI-Powered Question Answering – Ask natural-language questions about documents.
* 🔗 Source Citations – Provides references to supporting document content.
* 🎙️ Voice Input – Supports speech-based question input.
* 📁 Multi-Document Search – Retrieves information across multiple documents.
* 🖥️ Interactive Dashboard – Modern interface for document management and search.

⸻
## 🛠️ Technology Stack

| Layer | Technologies |
|---|---|
| Frontend | React, TypeScript, Vite |
| Styling | Tailwind CSS |
| Backend | Python, FastAPI |
| Vector Search | FAISS |
| Keyword Retrieval | BM25 |
| Embedding Models | Sentence Transformers |
| Reranking | Cross-Encoder |
| Database | SQLite |
| Document Processing | PyPDF |
| Testing | Pytest |
| Local LLM Integration | Ollama (where configured) |
| Containerization | Docker |

⸻
## 🏗️ System Architecture

| Layer | Component | Responsibility |
|---|---|---|
| 1 | User Interface | User interaction and document upload |
| 2 | React + TypeScript | Frontend application |
| 3 | FastAPI | Backend API and request handling |
| 4 | Document Processing | PDF extraction and text chunking |
| 5 | Embedding Generation | Converts text into vector representations |
| 6 | Hybrid Retrieval | Combines FAISS vector search and BM25 keyword search |
| 7 | Reranking | Cross-Encoder relevance scoring |
| 8 | Answer Generation | Generates context-based responses |
| 9 | Response Layer | Returns answers to the user |

### Workflow

**Document Upload → Text Extraction → Chunking → Embedding Generation → Hybrid Search → Reranking → Answer Generation → Response**

⸻

## 🔍 How HybridRAG Works

HybridRAG combines semantic search and keyword-based retrieval to identify relevant information from uploaded documents.

| Step | Process | Description |
|---|---|---|
| 1 | Document Upload | Users upload PDF or supported documents. |
| 2 | Text Extraction | Extracts readable content from documents. |
| 3 | Text Chunking | Splits content into smaller, manageable chunks. |
| 4 | Embedding Generation | Converts text chunks into numerical vectors. |
| 5 | Vector Search | FAISS retrieves semantically similar content. |
| 6 | Keyword Search | BM25 identifies keyword-based matches. |
| 7 | Reranking | Cross-Encoder improves retrieval relevance. |
| 8 | Answer Generation | Generates answers using retrieved context. |
| 9 | Response | Displays relevant answers to users. |


## 📂 Project Structure

```text
HybridRAG/
│
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── retriever.py
│   ├── search_index.py
│   ├── workspace.py
│   ├── answer_generator.py
│   ├── document_analyzer.py
│   └── query_understanding.py
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── context/
│   │   ├── hooks/
│   │   ├── pages/
│   │   ├── api/
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
│
├── tests/
├── data/
├── requirements.txt
├── Dockerfile
├── ui.py
└── README.md
```



⚙️ Installation and Setup

Prerequisites

Make sure you have the following installed:

* Python 3.11 or 3.12 recommended
* Node.js and npm
* Git
* macOS, Windows, or Linux

1. Clone the Repository

git clone https://github.com/SallaRenuka/HybridRAG.git
cd HybridRAG

2. Set Up the Python Environment

macOS / Linux:

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

Windows:

python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt

3. Start the Backend

From the project root:

uvicorn app.main:app --reload --port 8000

Backend URL:

http://127.0.0.1:8000

Interactive API documentation:

http://127.0.0.1:8000/docs

4. Start the Frontend

Open a second terminal and navigate to the frontend directory:

cd frontend
npm install
npm run dev

Open the local URL shown by Vite, usually:

http://localhost:5173

5. Run Tests

From the project root:

pytest -q

⸻

## 🔌 API Endpoints

| HTTP Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Checks backend health. |
| POST | `/ingest` | Processes and indexes uploaded documents. |
| POST | `/query` | Accepts questions and retrieves relevant information. |

Explore and test the endpoints using FastAPI Swagger documentation at:

http://127.0.0.1:8000/docs


⸻

🔐 Security Considerations

* Keep API keys and credentials in environment variables.
* Never commit .env files or private credentials.
* Exclude uploaded documents, databases, and generated indexes from public repositories.
* Apply authentication and authorization before exposing the application publicly.
* Validate uploaded files and protect against malicious document content.

⸻

🗺️ Future Improvements

* Production deployment with scalable infrastructure.
* Persistent vector index storage.
* Asynchronous document-processing pipeline.
* Retrieval evaluation and benchmarking.
* Advanced authentication and role-based access control.
* Monitoring, logging, and observability.
* Improved multi-user document management.

⸻

🎯 Project Objective

The objective of HybridRAG is to explore how modern information retrieval and AI techniques can transform traditional document searching into an intelligent question-answering experience.

The project demonstrates practical implementation of:

* Retrieval-Augmented Generation (RAG)
* Semantic and keyword-based search
* Vector similarity search
* Information retrieval and ranking
* Natural-language question answering
* Full-stack AI application development

⸻

👩‍💻 Author

Salla Renuka

* GitHub: @SallaRenuka
* Project Repository: HybridRAG

⸻

⭐ If you find this project interesting, consider giving the repository a star!
