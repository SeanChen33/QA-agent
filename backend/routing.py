from __future__ import annotations

import re

# Simple keyword-based router for deciding whether to use RAG
# Only trigger RAG when the user asks about PlatformAI or TokenAI
# Matches variants like: platformai, platform ai, platform.ai, tokenai, token ai, token.ai
_KEYWORD_PATTERNS = [
    r"platform\s*ai",
    r"token\s*ai",
    r"platform\.ai",
    r"token\.ai",
    r"platformai",
    r"tokenai",
]


def should_use_rag(question: str) -> bool:
    """Return True if the question is related to PlatformAI or TokenAI.

    The match is case-insensitive and tolerant to spaces or dots between words.
    """
    text = (question or "").lower()
    return any(re.search(pattern, text) for pattern in _KEYWORD_PATTERNS)
