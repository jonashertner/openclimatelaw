# pyright: reportPrivateUsage=false
from server.tools.passages import _VEC_FLOOR, _confidence


def test_vec_floor_recalibrated_for_e5() -> None:
    # e5-small cosines run high; the accept floor was raised from 0.5 (all-MiniLM) to 0.80.
    assert _VEC_FLOOR == 0.80


def test_confidence_reports_cosine_above_floor() -> None:
    # a semantic match clearing the e5 floor → report the cosine as confidence
    assert _confidence(coverage=0.0, lexical_rank=0.0, vec_sim=0.82) == 0.82
    # e5 sim below the floor → fall back to the weaker of coverage / normalised lexical rank
    assert _confidence(coverage=0.5, lexical_rank=0.5, vec_sim=0.60) == 0.5
