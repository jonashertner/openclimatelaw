import sys
import types

import pytest

import server.tools.search as search


def test_warm_embedder_loads_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(search, "_QUERY_EMBEDDER", None)

    class FakeST:
        def __init__(self, name: str) -> None:
            self.name = name

        def encode(self, texts: list[str], normalize_embeddings: bool = True) -> list[list[float]]:
            return [[0.1] * 384 for _ in texts]

    fake = types.ModuleType("sentence_transformers")
    fake.SentenceTransformer = FakeST  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake)

    # warm_embedder() returns (_QUERY_EMBEDDER is not None), so True means it loaded.
    assert search.warm_embedder() is True
