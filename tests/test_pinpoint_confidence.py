from server.tools.passages import _confidence  # pyright: ignore[reportPrivateUsage]


def test_single_incidental_token_is_not_certain() -> None:
    # coverage 1.0 (the one claim token is present) but a weak lexical rank must NOT
    # report confidence 1.0 — this was the calibration bug the audit found.
    assert _confidence(coverage=1.0, lexical_rank=0.09, vec_sim=0.0) < 0.3


def test_strong_lexical_match_is_high() -> None:
    assert _confidence(coverage=1.0, lexical_rank=0.99, vec_sim=0.0) >= 0.9


def test_semantic_dominates_when_above_floor() -> None:
    assert _confidence(coverage=0.3, lexical_rank=0.1, vec_sim=0.72) == 0.72


def test_confidence_is_the_weaker_of_coverage_and_rank() -> None:
    # partial coverage caps confidence even with a strong lexical rank
    assert _confidence(coverage=0.5, lexical_rank=0.99, vec_sim=0.0) == 0.5
