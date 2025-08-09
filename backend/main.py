from __future__ import annotations

import os
from typing import AsyncGenerator, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Load environment variables from backend/.env
load_dotenv()

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
cors_allow_origins_env = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:5173,http://localhost:3000")
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

    answer = await call_chat_completion(body.question.strip(), context=body.context)
    return AskResponse(answer=answer, session_id=body.session_id)


# For `uvicorn main:app --reload`
# No `if __name__ == "__main__"` block needed
