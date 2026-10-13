"""
V.E.R.A. corpus importers
=========================

Two importers, with deliberately different standing.

``import_citations`` reads numbered reference lines of the form

    [N] Publisher. "Title." Any further detail, date. https://deep/link

from Markdown files and turns each into **evidence**: the publisher becomes an
ORGANISATION and the cited work a DOCUMENT, both with resolvable provenance
(the URL), and the file and reference number recorded as the back-reference.
The file that cites a source is never itself the evidence.

* A URL that reaches only a site's front page (``https://www.example.org``)
  attests the publisher, not the document. The document is recorded as a
  candidate until a deep link backs it.
* A line carrying ``[verify URL ...]`` (an author's own note that the link was
  not checked) is refused, as is a self-citation (see ``self_patterns``).
  So is a line with no URL, no quoted title, or a
  URL that does not parse. Every refusal is reported with its reason, file
  and line; nothing is guessed.

``import_table_candidates`` reads Markdown tables (a usage register, say) and
records the named column as **candidates** only. A candidate is never an
existence claim. It is promoted when a corpus entity with exactly that name or
alias exists, through ``EVerificationService.match_candidates``.

Both are idempotent: a second run over the same files adds nothing.

Licence: GPL-3.0-or-later
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlsplit

from .e_verification_service import (
    EntityType,
    EVerificationService,
    ExistenceStatus,
    ProvenanceKind,
)

# -----------------------------------------------------------------------------
# Citations
# -----------------------------------------------------------------------------

_NUMBERED = re.compile(r"^\s*\[(\d{1,4})\]\s+(.*\S)\s*$")
_VERIFY_MARKER = re.compile(r"\[\s*verify\s+url", re.I)
_URL = re.compile(r"https?://[^\s<>\]\"'`]+")
_QUOTED_TITLE = re.compile(
    r"^(?P<pub>.+?)[.,]\s+(?:\((?P<apa>[^)]{2,40})\)\.\s+)?"
    r"(?:[\"\u201c](?P<title>[^\"\u201d]{2,400})[\"\u201d]|\*(?P<ititle>[^*]{2,400})\*)"
    r"[.,]?\s*(?P<rest>.*)$")
_MONTHS = ("January|February|March|April|May|June|July|August|September|October|"
           "November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec")
_DATE = re.compile(rf"\b(?:\d{{1,2}}\s+(?:{_MONTHS})\s+\d{{4}}|(?:{_MONTHS})\s+\d{{4}}|\d{{4}}-\d{{2}}-\d{{2}})\b")

ORIGIN_ROOT_URL = "citation_root_url"
ORIGIN_NO_URL = "citation_no_url"


@dataclass
class Citation:
    file: str
    number: int
    publishers: List[str]
    title: str
    date: Optional[str]
    url: str
    deep: bool
    raw: str

    @property
    def back_reference(self) -> str:
        return f"{self.file} [{self.number}]"


@dataclass
class Refusal:
    reason: str
    file: str
    line: int
    text: str


@dataclass
class CitationReport:
    files: int = 0
    numbered_lines: int = 0
    parsed: int = 0
    deep_links: int = 0
    root_links: int = 0
    refused: List[Refusal] = field(default_factory=list)
    publishers_created: int = 0
    documents_created: int = 0
    provenance_added: int = 0
    candidates_added: int = 0
    multi_publisher_strings: int = 0

    def refused_by_reason(self) -> Dict[str, int]:
        return dict(Counter(r.reason for r in self.refused).most_common())

    def to_dict(self) -> dict:
        return {
            "files": self.files,
            "numbered_lines": self.numbered_lines,
            "parsed": self.parsed,
            "deep_links": self.deep_links,
            "root_links": self.root_links,
            "refused": len(self.refused),
            "refused_by_reason": self.refused_by_reason(),
            "publishers_created": self.publishers_created,
            "documents_created": self.documents_created,
            "provenance_added": self.provenance_added,
            "candidates_added": self.candidates_added,
            "multi_publisher_strings": self.multi_publisher_strings,
            "refusals": [r.__dict__ for r in self.refused],
        }


def _clean_url(url: str) -> str:
    return url.rstrip(".,;:)")


def _is_deep(url: str) -> bool:
    parts = urlsplit(url)
    return bool(parts.path.strip("/")) or bool(parts.query)


def is_multi_publisher(name: str) -> bool:
    """'CISA, NSA, ASD and NCSC' names several bodies, not one; 'Smith, J' names one."""
    return name.count(",") >= 2 or bool(re.search(r",\s+(and|with)\b|\(with\b", name))


def parse_citation(text: str, file: str = "", line: int = 0,
                   self_patterns: Sequence["re.Pattern[str]"] = ()
                   ) -> Tuple[Optional[Citation], Optional[Refusal]]:
    """
    Parse one numbered reference line. Exactly one of the pair is not None.

    ``self_patterns`` are regexes for the author's own publications (names or
    URLs). A citation matching one is refused as a self-citation: an author's
    own work cannot attest the existence of what that work describes.
    """
    m = _NUMBERED.match(text)
    if not m:
        return None, Refusal("not a numbered reference", file, line, text.strip())
    number, body = int(m.group(1)), m.group(2)

    if _VERIFY_MARKER.search(body):
        return None, Refusal("marked unverified by its author", file, line, text.strip())
    urls = [_clean_url(u) for u in _URL.findall(body)]
    if not urls:
        return None, Refusal("no URL", file, line, text.strip())
    if len(urls) > 1:
        return None, Refusal("more than one URL", file, line, text.strip())
    url = urls[0]
    if not urlsplit(url).netloc or "." not in urlsplit(url).netloc:
        return None, Refusal("URL does not parse", file, line, text.strip())

    t = _QUOTED_TITLE.match(body.replace(url, "").strip())
    if not t:
        return None, Refusal("no quoted title", file, line, text.strip())
    publishers = [p.strip(" .") for p in re.split(r";|\s/\s", t.group("pub")) if p.strip(" .")]
    if not publishers:
        return None, Refusal("no publisher", file, line, text.strip())
    if self_patterns and any(rx.search(x) for rx in self_patterns for x in publishers + [url]):
        return None, Refusal("self-citation", file, line, text.strip())
    title = (t.group("title") or t.group("ititle")).strip(" .")
    date = (_DATE.search(t.group("rest")) or _DATE.search(t.group("apa") or "")
            or re.search(r"\b(?:19|20)\d\d\b", t.group("apa") or ""))
    return Citation(
        file=file, number=number, publishers=publishers, title=title,
        date=date.group(0) if date else None, url=url, deep=_is_deep(url), raw=text.strip(),
    ), None


def iter_numbered_lines(path: Path) -> Iterable[Tuple[int, str]]:
    with open(path, encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh, 1):
            if _NUMBERED.match(line):
                yield i, line.rstrip("\n")


def _ensure_entity(svc: EVerificationService, name: str, etype: EntityType,
                   cit: Citation, report: CitationReport, **extra) -> str:
    eid = svc.find_entity_id(name)
    if eid:
        return eid
    eid = svc.add_entity(
        canonical_name=name, entity_type=etype, status=ExistenceStatus.EXISTS,
        source_type="CITATION", source_url=cit.url, source_title=cit.title,
        source_date=cit.date, back_reference=cit.back_reference,
        confidence=0.9, reliability_score=0.85, verification_method="AUTOMATED", **extra,
    )
    report.provenance_added += 1
    if etype is EntityType.DOCUMENT:
        report.documents_created += 1
    else:
        report.publishers_created += 1
    return eid


def _document_name(svc: EVerificationService, cit: Citation) -> str:
    """The title, unless that name already belongs to something else."""
    existing = svc.find_entity_id(cit.title)
    if not existing:
        return cit.title
    row = svc._conn.execute(
        "SELECT entity_type FROM entities WHERE entity_id = ?", (existing,)).fetchone()
    pub = svc._conn.execute(
        "SELECT property_value FROM properties WHERE entity_id = ? AND property_name = 'publisher'",
        (existing,)).fetchone()
    if row["entity_type"] == EntityType.DOCUMENT.value and pub and pub[0] == cit.publishers[0]:
        return cit.title
    return f"{cit.title} ({cit.publishers[0]})"


def import_citations(svc: EVerificationService, paths: Iterable[Path],
                     label=lambda p: p.name,
                     self_patterns: Sequence[str] = ()) -> CitationReport:
    """
    Import every numbered reference line in ``paths``. See module docstring.

    A publisher string naming several bodies ("CISA, NSA and NCSC") creates no
    publisher entity, because no single body is named; the document is still
    imported and keeps the string as its ``publisher`` property.
    """
    selfs = [re.compile(p, re.I) for p in self_patterns]
    report = CitationReport()
    for path in paths:
        report.files += 1
        for lineno, text in iter_numbered_lines(path):
            report.numbered_lines += 1
            cit, refusal = parse_citation(text, label(path), lineno, selfs)
            if refusal:
                report.refused.append(refusal)
                if refusal.reason == "no URL":
                    t = _QUOTED_TITLE.match(_NUMBERED.match(text).group(2))
                    if t and svc.add_candidate(
                            (t.group("title") or t.group("ititle")).strip(" ."), ORIGIN_NO_URL,
                            type_hint=EntityType.DOCUMENT.value,
                            back_reference=f"{label(path)} [{_NUMBERED.match(text).group(1)}]",
                            raw=text.strip()):
                        report.candidates_added += 1
                continue
            report.parsed += 1

            for pub in cit.publishers:
                if is_multi_publisher(pub):
                    report.multi_publisher_strings += 1
                    continue
                pid = _ensure_entity(svc, pub, EntityType.ORGANISATION, cit, report)
                if svc.add_provenance(pid, "CITATION", cit.url, 0.85,
                                      source_title=cit.title, source_date=cit.date,
                                      back_reference=cit.back_reference):
                    report.provenance_added += 1

            if cit.deep:
                report.deep_links += 1
                name = _document_name(svc, cit)
                created_before = report.documents_created
                did = _ensure_entity(
                    svc, name, EntityType.DOCUMENT, cit, report,
                    properties=[("publisher", cit.publishers[0])]
                    + ([("published", cit.date)] if cit.date else []),
                )
                if report.documents_created == created_before and svc.add_provenance(
                        did, "CITATION", cit.url, 0.85, source_title=cit.title,
                        source_date=cit.date, back_reference=cit.back_reference):
                    report.provenance_added += 1
            else:
                report.root_links += 1
                if svc.add_candidate(cit.title, ORIGIN_ROOT_URL,
                                     type_hint=EntityType.DOCUMENT.value,
                                     back_reference=cit.back_reference, raw=cit.raw,
                                     note=f"link reaches only {cit.url}"):
                    report.candidates_added += 1
    return report


# -----------------------------------------------------------------------------
# Markdown tables -> candidates
# -----------------------------------------------------------------------------

@dataclass
class TableReport:
    tables_matched: int = 0
    rows_read: int = 0
    rows_refused: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    candidates_added: int = 0
    candidates_seen: int = 0

    def to_dict(self) -> dict:
        return {
            "tables_matched": self.tables_matched,
            "rows_read": self.rows_read,
            "rows_refused": dict(self.rows_refused),
            "candidates_added": self.candidates_added,
            "candidates_already_present": self.candidates_seen,
        }


def _cells(line: str) -> List[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _is_rule(cells: List[str]) -> bool:
    return all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c) and any(cells)


def iter_tables(path: Path) -> Iterable[Tuple[int, List[str], List[Tuple[int, List[str]]]]]:
    """Yield (header_line, header_cells, [(line, cells), ...]) for each Markdown table."""
    header = None
    rows: List[Tuple[int, List[str]]] = []
    start = 0
    with open(path, encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh, 1):
            if line.lstrip().startswith("|"):
                cells = _cells(line)
                if header is None:
                    header, start, rows = cells, i, []
                elif not _is_rule(cells):
                    rows.append((i, cells))
            elif header is not None:
                yield start, header, rows
                header = None
    if header is not None:
        yield start, header, rows


def import_table_candidates(svc: EVerificationService, path: Path, name_column: str,
                            origin: str, *, type_column: Optional[str] = None,
                            ref_column: Optional[str] = None, split: Optional[str] = None,
                            skip: Iterable[str] = ("TBC", "TBA", "n/a", "-", "")) -> TableReport:
    """
    Record each cell of ``name_column`` as a candidate. Rows whose cell count
    differs from the header's are refused rather than realigned.
    """
    report = TableReport()
    skip_l = {s.lower() for s in skip}
    want = name_column.strip().lower()
    for start, header, rows in iter_tables(path):
        h = [c.lower() for c in header]
        if want not in h:
            continue
        report.tables_matched += 1
        ni = h.index(want)
        ti = h.index(type_column.lower()) if type_column and type_column.lower() in h else None
        ri = h.index(ref_column.lower()) if ref_column and ref_column.lower() in h else None
        for lineno, cells in rows:
            report.rows_read += 1
            if len(cells) != len(header):
                report.rows_refused["cell count differs from header"] += 1
                continue
            values = [cells[ni]] if not split else cells[ni].split(split)
            for value in values:
                name = value.strip()
                if name.lower() in skip_l:
                    report.rows_refused["placeholder value"] += 1
                    continue
                back = cells[ri] if ri is not None else f"{path.name}:{lineno}"
                if svc.add_candidate(name, origin,
                                     type_hint=cells[ti] if ti is not None else None,
                                     back_reference=back, raw="|".join(cells)):
                    report.candidates_added += 1
                else:
                    report.candidates_seen += 1
    return report
