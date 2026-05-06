from server.tools.contracts.citation_formats import find_citation_spans


def test_finds_ecli():
    text = "as held in ECLI:NL:HR:2019:2007 (Hoge Raad, 20 Dec 2019)"
    spans = find_citation_spans(text)
    formats = {s.format_name for s in spans}
    assert "ecli" in formats
    matched = next(s for s in spans if s.format_name == "ecli")
    assert matched.text == "ECLI:NL:HR:2019:2007"


def test_finds_bverfge():
    text = "see BVerfGE 157, 30 (Neubauer)"
    spans = find_citation_spans(text)
    assert any(s.format_name == "bverfge" for s in spans)


def test_finds_bge():
    text = "cf. BGE 145 IV 100"
    spans = find_citation_spans(text)
    assert any(s.format_name == "bge" for s in spans)


def test_finds_us_reporter():
    text = "see Massachusetts v. EPA, 549 U.S. 497 (2007)"
    spans = find_citation_spans(text)
    assert any(s.format_name == "us_reporter" for s in spans)


def test_finds_multiple_in_one_string():
    text = "compare ECLI:NL:HR:2019:2007 with BVerfGE 157, 30"
    spans = find_citation_spans(text)
    assert len(spans) == 2


def test_no_match_on_plain_prose():
    text = "the court agreed with the petitioner's argument."
    spans = find_citation_spans(text)
    assert spans == []
