"""Tests for the citation and table importers."""

import pytest

from vera import EVerificationService, ExistenceStatus
from vera.importers import (
    ORIGIN_NO_URL,
    ORIGIN_ROOT_URL,
    import_citations,
    import_table_candidates,
    parse_citation,
)

ARTICLE = """# An article

Body text that cites things [1][2].

## References

[1] Kordia. "2026 NZ Business Cyber Security Report." Kordia, March 2026. https://www.kordia.co.nz/cyber-security-report-2026
[2] Office of the Privacy Commissioner. "Phase 1 Inquiry Report: ManageMyHealth." May 2026. https://www.privacy.org.nz [verify URL at publication]
[3] National Cyber Security Centre New Zealand. "Annual Cyber Threat Report." 2025. https://www.ncsc.govt.nz
[4] Office of the Privacy Commissioner; Ministry of Justice. Privacy Amendment Act 2025, Part 1. https://www.legislation.govt.nz
[5] Brown University. "AI mental health ethics." 21 October 2025. https://www.brown.edu/news/2025-10-21/ai-mental-health-ethics.
[6] Deloitte. "State of AI in the Enterprise 2026." January 2026.
[7] Kordia. "2026 NZ Business Cyber Security Report." Kordia, March 2026. https://www.kordia.co.nz/cyber-security-report-2026
"""

REGISTER = """# Register

| Reference | Type | Articles Used | Count |
|-----------|------|---------------|-------|
| Kordia | NZ firm | Cyber Sun CN#1 | 1 |
| Model Context Protocol (MCP) | Open standard | Gen AI #4 | 1 |
| Broken row | only three |
| TBC | placeholder | Cyber Sun CN#2 | 1 |

| Statistic | Source | Used In |
|-----------|--------|---------|
| 144:1 ratio | Trend Micro; Astrix Security (2026) | EA Thu Ch 16 |
"""


@pytest.fixture
def svc():
    s = EVerificationService(":memory:", seed=False)
    yield s
    s.close()


@pytest.fixture
def article(tmp_path):
    p = tmp_path / "Cyber_Sunday_Example_2026-06-07.md"
    p.write_text(ARTICLE, encoding="utf-8")
    return p


def test_parse_basic_citation():
    c, r = parse_citation('[1] Kordia. "Report." March 2026. https://www.kordia.co.nz/r-2026')
    assert r is None
    assert (c.publishers, c.title, c.date, c.deep) == (["Kordia"], "Report", "March 2026", True)


def test_trailing_full_stop_is_not_part_of_the_url():
    c, _ = parse_citation('[5] Brown. "X." 2025. https://www.brown.edu/news/x.')
    assert c.url == "https://www.brown.edu/news/x"


@pytest.mark.parametrize("line,reason", [
    ('[2] OPC. "X." 2026. https://www.privacy.org.nz [verify URL at publication]',
     "marked unverified by its author"),
    ('[6] Deloitte. "State of AI." January 2026.', "no URL"),
    ('[4] OPC; MoJ. Privacy Amendment Act 2025. https://www.legislation.govt.nz', "no quoted title"),
    ('[8] A. "X." https://a.example/1 https://b.example/2', "more than one URL"),
])
def test_refusals_are_named(line, reason):
    c, r = parse_citation(line)
    assert c is None and r.reason == reason


def test_import_citations(svc, article):
    rep = import_citations(svc, [article])
    d = rep.to_dict()
    assert d["numbered_lines"] == 7
    assert d["parsed"] == 4                      # [1] [3] [5] [7]
    assert d["refused_by_reason"] == {
        "marked unverified by its author": 1, "no quoted title": 1, "no URL": 1}

    # Publisher and deep-linked document exist, with the article as back-reference only.
    kordia = svc.check_existence("Kordia")
    assert kordia.existence_status is ExistenceStatus.EXISTS
    doc = svc.check_existence("2026 NZ Business Cyber Security Report")
    assert doc.existence_status is ExistenceStatus.EXISTS
    assert doc.entity_type.value == "DOCUMENT"
    assert doc.provenance.provenance_kind == "resolvable"
    assert doc.provenance.source_url == "https://www.kordia.co.nz/cyber-security-report-2026"
    assert doc.provenance.back_reference.startswith("Cyber_Sunday_Example_2026-06-07.md [")
    assert {"property_name": "publisher", "property_value": "Kordia", "confidence": 0.9} \
        in doc.properties

    # Root URL: the publisher exists, the document is only a candidate.
    assert svc.check_existence("National Cyber Security Centre New Zealand").existence_status \
        is ExistenceStatus.EXISTS
    assert svc.check_existence("Annual Cyber Threat Report").existence_status \
        is ExistenceStatus.UNKNOWN
    root = svc.list_candidates(origin=ORIGIN_ROOT_URL)
    assert [c["name"] for c in root] == ["Annual Cyber Threat Report"]

    # No URL: candidate, never evidence.
    assert svc.check_existence("State of AI in the Enterprise 2026").existence_status \
        is ExistenceStatus.UNKNOWN
    assert [c["name"] for c in svc.list_candidates(origin=ORIGIN_NO_URL)] == \
        ["State of AI in the Enterprise 2026"]

    # The unverified-marked line created nothing.
    assert svc.check_existence("Phase 1 Inquiry Report: ManageMyHealth").existence_status \
        is ExistenceStatus.UNKNOWN


def test_citing_article_is_never_an_entity_or_source(svc, article):
    import_citations(svc, [article])
    urls = [r[0] for r in svc._conn.execute("SELECT source_url FROM provenance")]
    assert all("Cyber_Sunday" not in (u or "") for u in urls)
    assert svc.check_existence("Cyber_Sunday_Example_2026-06-07.md").existence_status \
        is ExistenceStatus.UNKNOWN


def test_import_is_idempotent(svc, article):
    import_citations(svc, [article])
    before = svc.get_corpus_stats()
    rep = import_citations(svc, [article])
    assert svc.get_corpus_stats() == {**before, "queries_logged": before["queries_logged"]}
    assert (rep.publishers_created, rep.documents_created, rep.provenance_added,
            rep.candidates_added) == (0, 0, 0, 0)


def test_same_document_cited_twice_gets_two_back_references(svc, article):
    import_citations(svc, [article])
    eid = svc.find_entity_id("2026 NZ Business Cyber Security Report")
    refs = {r[0] for r in svc._conn.execute(
        "SELECT back_reference FROM provenance WHERE entity_id = ?", (eid,))}
    assert refs == {"Cyber_Sunday_Example_2026-06-07.md [1]", "Cyber_Sunday_Example_2026-06-07.md [7]"}


def test_title_clash_with_other_publisher_is_disambiguated(svc, tmp_path):
    p = tmp_path / "a.md"
    p.write_text('[1] Alpha. "Annual Report." 2025. https://alpha.example/ar\n'
                 '[2] Beta. "Annual Report." 2025. https://beta.example/ar\n', encoding="utf-8")
    import_citations(svc, [p])
    assert svc.find_entity_id("Annual Report")
    assert svc.find_entity_id("Annual Report (Beta)")


def test_table_candidates(svc, tmp_path, article):
    reg = tmp_path / "register.md"
    reg.write_text(REGISTER, encoding="utf-8")
    rep = import_table_candidates(svc, reg, "Reference", "register_reference",
                                  type_column="Type", ref_column="Articles Used")
    assert rep.to_dict()["rows_refused"] == {"cell count differs from header": 1,
                                             "placeholder value": 1}
    assert rep.candidates_added == 2
    # Candidates are not existence claims.
    assert svc.check_existence("Kordia").existence_status is ExistenceStatus.UNKNOWN

    src = import_table_candidates(svc, reg, "Source", "register_source", split=";")
    assert src.candidates_added == 2            # Trend Micro, Astrix Security (2026)

    # Evidence arrives through a citation, and only exact names are promoted.
    import_citations(svc, [article])
    assert svc.match_candidates() == 1
    promoted = svc.list_candidates(status="promoted")
    assert [c["name"] for c in promoted] == ["Kordia"]
