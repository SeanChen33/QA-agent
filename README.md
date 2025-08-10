## QA Agent (PlatformAI / TokenAI Q&A)

A full‑stack Question & Answer agent that routes user queries to either a Large Language Model directly or a Retrieval‑Augmented Generation (RAG) pipeline. RAG is only triggered when the question is related to PlatformAI or TokenAI; all other queries go straight to the LLM.

### Key Features
- Conditional RAG routing: only for PlatformAI/TokenAI keywords
- REST API backend (FastAPI) with provider abstraction (DashScope or Moonshot Kimi)
- Vector store with ChromaDB and DashScope Embeddings
- Minimal, responsive React + Vite + TypeScript frontend
- Simple URL ingestor to populate the vector database

### Architecture
- Backend (`backend/`)
  - FastAPI app exposing `/api/qa/ask`, `/api/vector/*`, `/api/health`
  - Providers:
    - DashScope (Alibaba Cloud, OpenAI-compatible endpoints)
    - Moonshot Kimi (OpenAI-compatible endpoints)
  - Vector store:
    - ChromaDB 0.5.x using `PersistentClient`
    - Embeddings via DashScope compatible endpoint
  - Conditional routing:
    - Only when the user mentions “platformai” or “tokenai” (including variants like `platform ai`, `platform.ai`, etc.), the backend performs similarity search and injects retrieved chunks into system context
- Frontend (`frontend/`)
  - React (Vite) chat UI calling the backend `/api/qa/ask`
  - Simple typing animation and theme/language toggling

---

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+

### 1) Backend Setup
```bash
# From the repository root
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r backend/requirements.txt
```

Create `backend/.env` and fill in your values:
```bash
# Required provider and model settings
PROVIDER=dashscope            # or kimi
MODEL=qwen2.5-7b-instruct     # provider-specific default is used if omitted

# Keys (one is required depending on provider)
DASHSCOPE_API_KEY=sk-xxxx
# KIMI_API_KEY=sk-xxxx

# Server
PORT=8000
CORS_ALLOW_ORIGINS=http://localhost:5173,http://localhost:3000
CORS_ALLOW_CREDENTIALS=true

# RAG
ENABLE_RAG=true
VECTOR_PERSIST_DIR=./backend/chroma_data
VECTOR_COLLECTION=qa_collection
EMBEDDING_MODEL=text-embedding-v3

# Optional: override DashScope base
# DASHSCOPE_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
```

Start the backend:
```bash
python -m uvicorn backend.main:app --reload --port 8000
```

Health check:
```bash
curl http://localhost:8000/api/health
```

### 2) Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
By default, the frontend contains a production `apiBaseUrl`. For local development, open `frontend/src/App.tsx` and switch to localhost:
```ts
// const apiBaseUrl = 'http://localhost:8000'
```

Open the printed Vite dev server URL (e.g., `http://localhost:5173`).

---

## Populate the Vector Database (RAG)
To ingest the content of a web page into the vector DB, run the URL ingestor after the backend is running:
```bash
python backend/import_url_to_vector.py "https://example.com/your-doc-page"
```
Notes:
- The script uses `API_BASE` from `backend/.env` and defaults to `http://localhost:8000`.
- Data is stored under `VECTOR_PERSIST_DIR` (default `backend/chroma_data`).

---

## How Conditional Routing Works
- The backend checks your question with a simple keyword matcher.
- If the question contains PlatformAI/TokenAI terms, it performs `similarity_search` on Chroma and composes a concise context block from the top results.
- This context is passed as a system message to the LLM. If no relevant chunks exist or an error occurs, it falls back to direct LLM.

---

## API Reference
- GET `/api/health`
  - Returns service status, provider, and model.

- POST `/api/qa/ask`
  - Request: `{ "question": string, "context"?: string, "session_id"?: string }`
  - Response: `{ "answer": string, "session_id"?: string }`

- POST `/api/vector/add`
  - Request: `{ "ids": string[], "texts": string[], "metadatas"?: object[] }`
  - Adds documents (with pre-computed embeddings in backend) to Chroma.

- POST `/api/vector/search`
  - Request: `{ "query": string, "k"?: number }`
  - Response: `{ "results": Array<{ id, document, metadata, distance }> }`

---

## Configuration Summary (backend/.env)
- PROVIDER: `dashscope` | `kimi`
- MODEL: model name for the selected provider
- DASHSCOPE_API_KEY / KIMI_API_KEY: provider credentials
- PORT: FastAPI port (default 8000)
- CORS_ALLOW_ORIGINS, CORS_ALLOW_CREDENTIALS: CORS settings
- ENABLE_RAG: `true` to enable vector store
- VECTOR_PERSIST_DIR: Chroma persistence path
- VECTOR_COLLECTION: Chroma collection name
- EMBEDDING_MODEL: Embedding model for DashScope
- DASHSCOPE_API_BASE: Optional base URL for DashScope (OpenAI-compatible)

---

## Troubleshooting
- AttributeError: `'Client' object has no attribute 'persist'`
  - Fixed by using `chromadb.PersistentClient` (0.5.x). Ensure you installed `backend/requirements.txt`.
- ImportError: `attempted relative import with no known parent package`
  - Start the backend using module form: `python -m uvicorn backend.main:app --reload --port 8000` (from repo root).
- Chroma not installed / vector features failing
  - Make sure `pip install -r backend/requirements.txt` ran in the active venv.
- CORS issues from the browser
  - Adjust `CORS_ALLOW_ORIGINS` in `backend/.env` to include your frontend origin.

---

## License
This project is released under the MIT License. See `LICENSE` for details.
