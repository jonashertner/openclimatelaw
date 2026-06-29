from ingest.outcome import accept

_SUMMARY = (
    "The court ordered the State to reduce greenhouse gas emissions and granted the relief sought."
)


def test_accept_high_confidence_verified_quote() -> None:
    assert accept(
        {
            "outcome_code": "plaintiff_won",
            "confidence": "high",
            "supporting_quote": "ordered the State to reduce greenhouse gas emissions",
        },
        _SUMMARY,
    )


def test_accept_na_needs_no_quote() -> None:
    assert accept({"outcome_code": "na", "confidence": "high", "supporting_quote": ""}, _SUMMARY)


def test_reject_medium_confidence() -> None:
    assert not accept(
        {
            "outcome_code": "plaintiff_won",
            "confidence": "medium",
            "supporting_quote": "granted the relief sought",
        },
        _SUMMARY,
    )


def test_reject_unknown_code() -> None:
    assert not accept(
        {
            "outcome_code": "unknown",
            "confidence": "high",
            "supporting_quote": "granted the relief sought",
        },
        _SUMMARY,
    )


def test_reject_unverifiable_quote() -> None:
    # high-confidence but the quote is NOT in the summary -> refuse (anti-fabrication)
    assert not accept(
        {
            "outcome_code": "defendant_won",
            "confidence": "high",
            "supporting_quote": "the appeal was dismissed in its entirety",
        },
        _SUMMARY,
    )
