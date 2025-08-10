from __future__ import annotations

import os
from typing import AsyncGenerator, Optional

import httpx
from dotenv import load_dotenv
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Any

# Keyword-based routing for conditional RAG (support both package and script runs)
try:  # Prefer absolute import when running as a module
    from backend.routing import should_use_rag  # type: ignore
except Exception:  # Fallback when current dir is already backend
    from routing import should_use_rag  # type: ignore

# Load environment variables from backend/.env (robust to working directory)
_ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(_ENV_PATH)

# Provider selection: "dashscope" (阿里云百炼) | "kimi" (Moonshot)
PROVIDER = os.getenv("PROVIDER", "dashscope").lower()

# Model defaults by provider
DEFAULT_MODEL_BY_PROVIDER = {
    "dashscope": "qwen2.5-7b-instruct",
    "kimi": "kimi-k2-instruct",
}

MODEL = os.getenv("MODEL", DEFAULT_MODEL_BY_PROVIDER.get(PROVIDER, "qwen2.5-7b-instruct"))
PORT = int(os.getenv("PORT", "8000"))

# Keys (loaded lazily per provider)
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
KIMI_API_KEY = os.getenv("KIMI_API_KEY")

# API bases
DASHSCOPE_API_BASE = os.getenv("DASHSCOPE_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
KIMI_API_BASE = os.getenv("KIMI_API_BASE", "https://api.moonshot.cn/v1")

# Validate required key for selected provider
if PROVIDER == "dashscope" and not DASHSCOPE_API_KEY:
    raise RuntimeError("DASHSCOPE_API_KEY is not set. Please set it in backend/.env for DashScope (百炼) provider")
if PROVIDER == "kimi" and not KIMI_API_KEY:
    raise RuntimeError("KIMI_API_KEY is not set. Please set it in backend/.env for Kimi provider")

app = FastAPI(title="QA Agent Backend", version="1.0.0")

# Configurable CORS
cors_allow_origins_env = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:5173,http://localhost:3000,https://qa-agent-4vqlpnt3m-sean-chens-projects-6fe0ca6c.vercel.app")
cors_allow_origin_regex = os.getenv("CORS_ALLOW_ORIGIN_REGEX")
cors_allow_credentials_env = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower()

allow_credentials = cors_allow_credentials_env in {"1", "true", "yes"}
origins = [o.strip() for o in cors_allow_origins_env.split(",") if o.strip()]

# If using wildcard "*", credentials must be disabled per CORS spec
if len(origins) == 1 and origins[0] == "*":
    allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=cors_allow_origin_regex or None,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str = Field(..., description="User question")
    context: Optional[str] = Field(None, description="Optional context")
    session_id: Optional[str] = Field(None, description="Conversation id")
    stream: bool = Field(False, description="Enable SSE streaming")


class AskResponse(BaseModel):
    answer: str
    session_id: Optional[str] = None


class AddDocsRequest(BaseModel):
    ids: list[str]
    texts: list[str]
    metadatas: Optional[list[dict]] = None


class SearchRequest(BaseModel):
    query: str
    k: int = 5


# Optional vector store (DashScope Embedding + Chroma)
VECTOR_PERSIST_DIR = os.getenv("VECTOR_PERSIST_DIR", "./chroma_data")
VECTOR_COLLECTION = os.getenv("VECTOR_COLLECTION", "qa_collection")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-v3")
vector_store: Optional[Any] = None

if os.getenv("ENABLE_RAG", "false").lower() in {"1", "true", "yes"}:
    # Lazy import to avoid requiring chromadb unless RAG is enabled
    try:
        from vector_store import ChromaVectorStore, DashScopeEmbedder  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "ENABLE_RAG=true but optional dependencies are missing. "
            "Please install backend/requirements.txt in the active environment."
        ) from exc
    if not DASHSCOPE_API_KEY:
        raise RuntimeError("ENABLE_RAG=true requires DASHSCOPE_API_KEY for embeddings")
    embedder = DashScopeEmbedder(api_key=DASHSCOPE_API_KEY, model=EMBEDDING_MODEL)
    vector_store = ChromaVectorStore(
        persist_dir=VECTOR_PERSIST_DIR,
        collection=VECTOR_COLLECTION,
        embedder=embedder,
    )


@app.get("/api/health")
async def health():
    return {"status": "ok", "model": MODEL, "provider": PROVIDER}


async def call_chat_completion(question: str, context: Optional[str] = None) -> str:
    """Call provider's OpenAI-compatible Chat Completions API and return answer text.

    - DashScope (阿里云百炼兼容模式): https://dashscope.aliyuncs.com/compatible-mode/v1
    - Moonshot Kimi: https://api.moonshot.cn/v1
    """
    if PROVIDER == "dashscope":
        url = f"{DASHSCOPE_API_BASE}/chat/completions"
        headers = {
            "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
            "Content-Type": "application/json",
        }
    elif PROVIDER == "kimi":
        url = f"{KIMI_API_BASE}/chat/completions"
        headers = {
            "Authorization": f"Bearer {KIMI_API_KEY}",
            "Content-Type": "application/json",
        }
    else:
        raise HTTPException(status_code=500, detail=f"Unsupported provider: {PROVIDER}")

    messages = []
    if context:
        messages.append({"role": "system", "content": context})
    messages.append({"role": "user", "content": question})

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.7,
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except Exception:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"Unexpected response: {data}")


@app.post("/api/qa/ask", response_model=AskResponse)
async def qa_ask(body: AskRequest):
    if not body.question or not body.question.strip():
        raise HTTPException(status_code=400, detail="question is required")
    question_text = body.question.strip()

    # Only query RAG for PlatformAI/TokenAI related questions
    constructed_context: Optional[str] = body.context
    if should_use_rag(question_text) and vector_store is not None:
        try:
            results = vector_store.similarity_search(query=question_text, k=5)
            # Build concise context from top results
            context_chunks: list[str] = []
            for idx, item in enumerate(results, start=1):
                md = item.get("metadata") or {}
                source = md.get("url") or md.get("source") or md.get("host") or ""
                header = f"[Doc {idx}] {source}".strip()
                doc = item.get("document") or ""
                context_chunks.append(f"{header}\n{doc}")
            rag_context = (
                "You are provided with knowledge snippets about PlatformAI or TokenAI. "
                "Use them faithfully; if missing, say you don't know.\n\n" + "\n\n---\n\n".join(context_chunks)
            )
            if constructed_context:
                constructed_context = constructed_context + "\n\n" + rag_context
            else:
                constructed_context = rag_context
        except Exception as exc:  # noqa: BLE001
            # Fallback to non-RAG if vector store errors out
            constructed_context = body.context

    answer = await call_chat_completion(question_text, context=constructed_context)
    return AskResponse(answer=answer, session_id=body.session_id)


@app.post("/api/vector/add")
async def vector_add(body: AddDocsRequest):
    if not vector_store:
        raise HTTPException(status_code=400, detail="RAG/Vector store not enabled")
    if len(body.ids) != len(body.texts):
        raise HTTPException(status_code=400, detail="ids and texts must be same length")
    vector_store.add_texts(ids=body.ids, texts=body.texts, metadatas=body.metadatas)
    return {"status": "ok", "count": len(body.ids)}


@app.post("/api/vector/search")
async def vector_search(body: SearchRequest):
    if not vector_store:
        raise HTTPException(status_code=400, detail="RAG/Vector store not enabled")
    results = vector_store.similarity_search(query=body.query, k=body.k)
    return {"results": results}


# For `uvicorn main:app --reload`
# No `if __name__ == "__main__"` block needed
