from ingest.passages import split_into_passages


def test_split_preserves_offsets_and_drops_tiny() -> None:
    src = (
        "Para one is long enough to keep as a passage here.\n\n"
        "x\n\n"
        "Para two is also clearly long enough to be kept here."
    )
    parts = split_into_passages(src)
    assert all(src[s:e] == t for s, e, t in parts)
    assert all(len(t) >= 40 for _, _, t in parts)
    assert len(parts) == 2
    assert parts[0][2].startswith("Para one")
    assert parts[1][2].startswith("Para two")


def test_split_empty_text() -> None:
    assert split_into_passages("") == []
    assert split_into_passages("   \n\n   ") == []
