import pytest

from server.tools import grounding_judge


@pytest.mark.asyncio
async def test_degrades_safely_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # With no Anthropic key configured the judge must be a safe no-op, never an error.
    monkeypatch.setattr(grounding_judge, "_key", lambda: None)
    result = await grounding_judge.verify_grounding("Any draft text here.", [])
    assert result["available"] is False
    assert result["supported"] is None
    assert result["unsupported_claims"] == []
