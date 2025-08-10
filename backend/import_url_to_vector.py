from __future__ import annotations
import os, uuid
from urllib.parse import urlparse
from typing import List

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

API_BASE = os.getenv('API_BASE', 'http://localhost:8000')


def fetch_html_text(url: str) -> str:
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; QA-Agent/1.0)'
    }
    with httpx.Client(timeout=30, follow_redirects=True, headers=headers) as c:
        r = c.get(url)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        # Remove script/style/nav/footer
        for tag in soup(['script', 'style', 'nav', 'footer', 'noscript']):
            tag.decompose()
        text = soup.get_text('\n')
        # Normalize whitespace
        lines = [ln.strip() for ln in text.splitlines()]
        text = '\n'.join(ln for ln in lines if ln)
        return text


def chunk_text(text: str, size: int = 900, overlap: int = 120) -> List[str]:
    chunks: List[str] = []
    i = 0
    n = len(text)
    while i < n:
        chunks.append(text[i:i+size])
        i += max(1, size - overlap)
    return chunks


def add_to_vector(ids: List[str], texts: List[str], metadatas: List[dict]) -> None:
    with httpx.Client(timeout=120) as c:
        r = c.post(f"{API_BASE}/api/vector/add", json={
            'ids': ids,
            'texts': texts,
            'metadatas': metadatas,
        })
        r.raise_for_status()
        print(r.json())


def main(url: str) -> None:
    print('Fetching', url)
    text = fetch_html_text(url)
    print('Fetched chars:', len(text))
    parts = chunk_text(text)
    print('Chunks:', len(parts))
    parsed = urlparse(url)
    base_meta = {
        'source': 'url',
        'url': url,
        'host': parsed.netloc,
        'path': parsed.path,
    }
    ids = [str(uuid.uuid4()) for _ in parts]
    metas = [{**base_meta, 'chunk': i} for i in range(len(parts))]
    add_to_vector(ids, parts, metas)


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('Usage: python import_url_to_vector.py <URL>')
        sys.exit(1)
    main(sys.argv[1])
