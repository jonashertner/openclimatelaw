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


def test_latest_decision_date_none_without_decision_event() -> None:
    assert (
        latest_decision_date(
            [{"date": "2015-01-01T00:00:00Z", "event_type": "Filing Year For Action"}]
        )
        is None
    )
    assert latest_decision_date([]) is None
    assert latest_decision_date(None) is None
