from __future__ import annotations

import os
from typing import Iterable, List, Optional

import httpx
import chromadb
from chromadb.api import ClientAPI
from chromadb.config import Settings

# Embedding via DashScope (百炼) compatible embeddings endpoint
# https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings


class DashScopeEmbedder:
    def __init__(self, api_key: str, model: str = "text-embedding-v3") -> None:
        self.api_key = api_key
        self.model = model
        self.base = os.getenv("DASHSCOPE_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")

    def embed(self, texts: Iterable[str]) -> List[List[float]]:
        url = f"{self.base}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        # batch once for simplicity; Chroma can accept list of vectors
        payload = {"model": self.model, "input": list(texts)}
        with httpx.Client(timeout=60) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            # OpenAI-compatible response: data:[{embedding: [...]}]
            return [item["embedding"] for item in data["data"]]


class ChromaVectorStore:
    def __init__(
        self,
        persist_dir: str,
        collection: str,
        embedder: DashScopeEmbedder,
    ) -> None:
        self.embedder = embedder
        # Use PersistentClient in ChromaDB 0.5.x
        # It persists automatically; no explicit persist() needed
        try:
            self.client: ClientAPI = chromadb.PersistentClient(path=persist_dir)
        except AttributeError:
            # Fallback for older API if environment has legacy Client
            self.client = chromadb.Client(Settings(is_persistent=True, persist_directory=persist_dir))
        self.collection = self.client.get_or_create_collection(name=collection)

    def add_texts(self, ids: List[str], texts: List[str], metadatas: Optional[List[dict]] = None) -> None:
        embeddings = self.embedder.embed(texts)
        self.collection.add(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)
        # PersistentClient writes are durable automatically in 0.5.x

    def similarity_search(self, query: str, k: int = 5) -> List[dict]:
        query_emb = self.embedder.embed([query])[0]
        res = self.collection.query(query_embeddings=[query_emb], n_results=k, include=["documents", "metadatas", "distances"])
        results: List[dict] = []
        for i in range(len(res.get("ids", [[]])[0])):
            item = {
                "id": res["ids"][0][i],
                "document": res["documents"][0][i],
                "metadata": res.get("metadatas", [[{}]])[0][i],
                "distance": res.get("distances", [[None]])[0][i],
            }
            results.append(item)
        return results
