from datetime import date

from ingest.sabin.cpr import latest_decision_date


def test_latest_decision_date_picks_latest_decision() -> None:
    events = [
        {"date": "2015-06-24T00:00:00Z", "event_type": "Decision"},
        {"date": "2019-01-08T00:00:00Z", "event_type": "Appeal"},
        {"date": "2020-01-13T00:00:00Z", "event_type": "Decision"},
        {"date": "2019-12-20T00:00:00Z", "event_type": "Decision"},
    ]
    assert latest_decision_date(events) == date(2020, 1, 13)


def test_latest_decision_date_prefers_judgment_over_later_execution() -> None:
    # KlimaSeniorinnen shape: a later Committee-of-Ministers execution 'Decision' must
    # NOT override the merits judgment date.
    events = [
        {
            "date": "2022-04-26T00:00:00Z",
            "event_type": "Decision",
            "metadata": {"description": ["Relinquishment of jurisdiction"]},
        },
        {
            "date": "2024-04-09T00:00:00Z",
            "event_type": "Decision",
            "metadata": {"description": ["Judgment from the European Court of Human Rights"]},
        },
        {
            "date": "2025-03-06T00:00:00Z",
            "event_type": "Decision",
            "metadata": {"description": ["Committee of Ministers supervision of execution"]},
        },
    ]
    assert latest_decision_date(events) == date(2024, 4, 9)


def test_latest_decision_date_excludes_procedural_rulings() -> None:
    # Shoalwater shape: a 'decided' case whose only Decision events are procedural
    # (a remand, a discovery protective order) has NO real decision date.
    events = [
        {
            "date": "2026-04-29T00:00:00Z",
            "event_type": "Decision",
            "title": "Defendants' motion for a protective order staying discovery denied.",
        },
        {
            "date": "2026-03-26T00:00:00Z",
            "event_type": "Decision",
            "title": "Motion to remand granted.",
        },
    ]
    assert latest_decision_date(events) is None


def test_latest_decision_date_keeps_dispositive_ruling() -> None:
    # A dispositive ruling that doesn't say "judgment" (a dismissal) is still a decision.
    events = [
        {
            "date": "2023-02-03T00:00:00Z",
            "event_type": "Decision",
            "title": "Defendants' motion to dismiss granted; case dismissed with prejudice.",
        },
        {
            "date": "2023-05-01T00:00:00Z",
            "event_type": "Decision",
            "title": "Motion to stay pending appeal granted.",
        },
    ]
    # The procedural stay (later) is excluded; the dismissal (earlier) is the decision.
    assert latest_decision_date(events) == date(2023, 2, 3)


def test_latest_decision_date_none_without_decision_event() -> None:
    assert (
        latest_decision_date(
            [{"date": "2015-01-01T00:00:00Z", "event_type": "Filing Year For Action"}]
        )
        is None
    )
    assert latest_decision_date([]) is None
    assert latest_decision_date(None) is None
