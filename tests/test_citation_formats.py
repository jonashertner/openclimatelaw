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


def _fmts(text: str) -> set[str]:
    return {s.format_name for s in find_citation_spans(text)}


def test_finds_uk_neutral():
    assert "uk_neutral" in _fmts("R (Finch) v Surrey CC [2024] UKSC 20")
    assert "uk_neutral" in _fmts("Plan B Earth v PM [2021] EWHC 1234 (Admin)")


def test_finds_au_nz_neutral():
    assert "au_nz_neutral" in _fmts("Sharma v Minister [2021] FCA 560")
    assert "au_nz_neutral" in _fmts("Bushfire Survivors v EPA [2021] NSWLEC 92")
    assert "au_nz_neutral" in _fmts("Smith v Fonterra [2024] NZSC 5")


def test_finds_canada_neutral():
    assert "ca_neutral" in _fmts("Reference re GGPPA, 2021 SCC 11")


def test_finds_ireland_and_sa_neutral():
    assert "ie_neutral" in _fmts("Friends of the Irish Environment v Govt [2020] IESC 49")
    assert "za_neutral" in _fmts("Earthlife Africa [2017] ZACC 12")


def test_finds_india_scc():
    assert "in_scc" in _fmts("MK Ranjitsinh v Union of India (2024) 5 SCC 123")


def test_finds_cjeu_case_number():
    assert "cjeu" in _fmts("see Carvalho, Case C-565/19 P")


def test_finds_f_supp_2d_and_f4th():
    assert "us_reporter" in _fmts("see 123 F. Supp. 2d 456 (S.D.N.Y. 2000)")
    assert "us_reporter" in _fmts("see 12 F.4th 345 (9th Cir. 2021)")


def test_bracketed_year_alone_is_not_a_citation():
    # A bracketed year with no court abbreviation must NOT be flagged (false-positive guard).
    assert find_citation_spans("As noted in the 2024 report [2024], emissions rose.") == []
