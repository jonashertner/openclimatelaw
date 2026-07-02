# pyright: basic
"""multilingual-e5-small embedder for passage pinpoint (semantic retrieval).

Validated (2026-07-01) to fix cross-lingual pinpoint: an English claim retrieves the
Japanese/Portuguese passages the English-only all-MiniLM model buried. e5 requires the
`query:` / `passage:` prefixes and produces 384-dim vectors (drop-in for pgvector(384)).
Used by BOTH the backfill (ingest.embed_passages) and the query path (find_relevant_passage)
so the index and the query share one model. Lazy-loaded; degrades to None if unavailable.
"""

import threading
from typing import Any

_MODEL: Any = None
_LOCK = threading.Lock()
_MODEL_ID = "intfloat/multilingual-e5-small"
_MAX_CHARS = 1600  # ~head of the passage (e5 truncates ~512 tokens); matches v1 chunking


def _model() -> Any:
    global _MODEL
    if _MODEL is None:
        with _LOCK:
            if _MODEL is None:
                from sentence_transformers import SentenceTransformer

                _MODEL = SentenceTransformer(_MODEL_ID)
    return _MODEL


def embed_passages(texts: list[str]) -> list[list[float]] | None:
    """Embed passage texts (with the e5 `passage:` prefix). Returns None if unavailable."""
    try:
        prepped = ["passage: " + (t or "")[:_MAX_CHARS] for t in texts]
        vecs = _model().encode(prepped, normalize_embeddings=True, batch_size=16)
        return [[float(x) for x in v] for v in vecs]
    except Exception:
        return None


def embed_query(text: str) -> list[float] | None:
    """Embed a claim/query (with the e5 `query:` prefix). Returns None if unavailable."""
    try:
        v = _model().encode(["query: " + (text or "")], normalize_embeddings=True)[0]
        return [float(x) for x in v]
    except Exception:
        return None
