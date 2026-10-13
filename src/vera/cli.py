"""
V.E.R.A. command line
=====================

    vera check "Aspirin is an analgesic."
    vera check "Zarkonite is a rare mineral." --json
    vera --db corpus.db corpus init
    vera --db corpus.db corpus add "Wainuiomata" --type PLACE --status EXISTS \\
         --url https://en.wikipedia.org/wiki/Wainuiomata
    vera --db corpus.db corpus add "DPMC" --type ORGANISATION --status EXISTS \\
         --named-source "DPMC Critical Infrastructure Consultation" --source-date 2026-02
    vera --db corpus.db corpus lookup DPMC
    vera --db corpus.db corpus search wain
    vera --db corpus.db corpus stats
    vera --db corpus.db identity "Einstein" "Albert Einstein"

Which corpus
------------
``--db PATH`` (or the ``VERA_DB`` environment variable) names a corpus file.
Without either, commands run against an in-memory copy of the demonstration
corpus and say so, so a verdict is never mistaken for one against your data.
``corpus init`` and ``corpus add`` refuse to run without a file.

Exit codes for ``vera check``
-----------------------------
  0  allowed: VERIFIED, or NO_CHECK_REQUIRED (n-type formula)
  1  blocked: REFUSAL (a subject is UNKNOWN) or NOT_EXISTS
  2  not evaluated: the statement could not be parsed, or an error

Not evaluated is non-zero on purpose: a gate that cannot run must not pass.

``--require-resolvable`` also blocks a VERIFIED result whose evidence includes
a named source (identified by name, not re-readable). Off by default.

Licence: GPL-3.0-or-later
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .e_verification_service import (
    EntityType,
    EVerificationService,
    ExistenceStatus,
    ProvenanceKind,
)
from .vera_pipeline import VERAPipeline, VerificationOutcome

EXIT_ALLOWED, EXIT_BLOCKED, EXIT_NOT_EVALUATED = 0, 1, 2

_ALLOWED = {VerificationOutcome.VERIFIED, VerificationOutcome.NO_CHECK_REQUIRED}
_BLOCKED = {VerificationOutcome.REFUSAL, VerificationOutcome.NOT_EXISTS}

DEMO_NOTE = "Using the built-in demonstration corpus (no --db or VERA_DB given)."


def _db_path(args) -> Optional[str]:
    return args.db or os.environ.get("VERA_DB") or None


def _require_db(args, what: str) -> str:
    path = _db_path(args)
    if not path:
        raise SystemExit(f"vera: {what} needs a corpus file: pass --db PATH or set VERA_DB")
    return path


def _open_service(args) -> EVerificationService:
    path = _db_path(args)
    if path:
        if not Path(path).exists():
            raise SystemExit(f"vera: no corpus at {path}; create one with `vera --db {path} corpus init`")
        return EVerificationService(path, seed=args.with_demo)
    print(DEMO_NOTE, file=sys.stderr)
    return EVerificationService(":memory:", seed=True)


def _print(obj, as_json: bool, text: str) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False) if as_json else text)


# -----------------------------------------------------------------------------
# Commands
# -----------------------------------------------------------------------------

def cmd_check(args) -> int:
    path = _db_path(args)
    if path and not Path(path).exists():
        raise SystemExit(f"vera: no corpus at {path}; create one with `vera --db {path} corpus init`")
    if not path:
        print(DEMO_NOTE, file=sys.stderr)
    pipeline = VERAPipeline(db_path=path or ":memory:", seed=(not path) or args.with_demo)
    try:
        text = " ".join(args.statement)
        r = pipeline.run(text)
        if r.outcome in _ALLOWED:
            code = EXIT_ALLOWED
        elif r.outcome in _BLOCKED:
            code = EXIT_BLOCKED
        else:
            code = EXIT_NOT_EVALUATED
        held_on_named = (
            args.require_resolvable
            and r.outcome is VerificationOutcome.VERIFIED
            and r.evidence_basis != "resolvable"
        )
        if held_on_named:
            code = EXIT_BLOCKED

        if args.json:
            d = r.to_dict()
            if not args.audit:
                d.pop("audit_trail", None)
            d["exit_code"] = code
            d["held_on_named_evidence"] = bool(held_on_named)
            print(json.dumps(d, indent=2, ensure_ascii=False))
        else:
            verdict = {EXIT_ALLOWED: "ALLOWED", EXIT_BLOCKED: "BLOCKED",
                       EXIT_NOT_EVALUATED: "NOT EVALUATED"}[code]
            print(f"{verdict}  {r.outcome.value}"
                  + ("  (held: --require-resolvable)" if held_on_named else ""))
            print(f"  Statement:      {r.query}")
            print(f"  Characteristic: {r.characteristic or 'n/a'}")
            if r.evidence_basis:
                print(f"  Evidence:       {r.evidence_basis}")
            for er in r.existence_results:
                src = ""
                if er.provenance:
                    p = er.provenance
                    src = f"  [{p.provenance_kind}: {p.source_url or p.source_title}]"
                print(f"  E!({er.entity_name}) = {er.existence_status.value}{src}")
            if r.unchecked_entity_candidates:
                print(f"  Not checked:    {', '.join(r.unchecked_entity_candidates)}")
            print(f"  {r.summary}")
            if args.audit:
                r.print_audit_trail()
        return code
    finally:
        pipeline.close()


def cmd_corpus_init(args) -> int:
    path = _require_db(args, "corpus init")
    existed = Path(path).exists()
    svc = EVerificationService(path, seed=args.with_demo)
    stats = svc.get_corpus_stats()
    applied = svc.migrations_applied
    svc.close()
    state = "opened existing" if existed else "created"
    print(f"{state} corpus {path}: schema v{stats['schema_version']}"
          f"{', migrations applied ' + str(applied) if applied else ', already current'}; "
          f"{stats['existing_entities'] + stats['confirmed_nonexistent']} entities")
    return 0


def cmd_corpus_stats(args) -> int:
    svc = _open_service(args)
    stats = svc.get_corpus_stats()
    svc.close()
    _print(stats, args.json, "\n".join(f"{k:24} {v}" for k, v in stats.items()))
    return 0


def cmd_corpus_lookup(args) -> int:
    svc = _open_service(args)
    r = svc.check_existence(args.name)
    svc.close()
    p = r.provenance
    lines = [f"E!({args.name}) = {r.existence_status.value}"]
    if r.canonical_name:
        lines.append(f"  canonical:  {r.canonical_name} ({r.entity_type.value}, confidence {r.confidence})")
    if p:
        lines.append(f"  provenance: {p.provenance_kind}: {p.source_url or p.source_title}"
                     f" (reliability {p.reliability_score})")
        if p.back_reference:
            lines.append(f"  found in:   {p.back_reference}")
    _print(r.to_dict(), args.json, "\n".join(lines))
    return 0 if r.existence_status is not ExistenceStatus.UNKNOWN else 1


def cmd_corpus_search(args) -> int:
    svc = _open_service(args)
    results = svc.search_entities(args.query, limit=args.limit)
    svc.close()
    _print([r.to_dict() for r in results], args.json,
           "\n".join(f"{r.existence_status.value:10} {r.canonical_name}  ({r.entity_type.value})"
                     for r in results) or "no matches")
    return 0


def cmd_corpus_add(args) -> int:
    path = _require_db(args, "corpus add")
    if not Path(path).exists():
        raise SystemExit(f"vera: no corpus at {path}; create one with `vera --db {path} corpus init`")
    if bool(args.url) == bool(args.named_source):
        raise SystemExit("vera: give exactly one of --url (resolvable) or --named-source (named)")
    svc = EVerificationService(path, seed=False)
    try:
        eid = svc.add_entity(
            canonical_name=args.name,
            entity_type=EntityType(args.type),
            status=ExistenceStatus(args.status),
            source_type=args.source_type,
            source_url=args.url,
            reliability_score=args.reliability,
            aliases=[(a, "ALTERNATE") for a in args.alias],
            confidence=args.confidence,
            provenance_kind=ProvenanceKind.RESOLVABLE if args.url else ProvenanceKind.NAMED,
            source_title=args.named_source or args.title,
            source_date=args.source_date,
            back_reference=args.back_ref,
            description=args.description,
            wikidata_qid=args.wikidata,
        )
    except ValueError as exc:
        raise SystemExit(f"vera: {exc}")
    finally:
        svc.close()
    print(f"added {args.name} as {eid}")
    return 0


def cmd_identity(args) -> int:
    svc = _open_service(args)
    r = svc.resolve_identity(args.a, args.b)
    svc.close()
    _print(r.to_dict(), args.json,
           f"{r.relation_type.value}  {r.ntp_relation}  (confidence {r.confidence:.2f}, "
           f"both exist: {r.both_exist})")
    return 0


# -----------------------------------------------------------------------------
# Parser
# -----------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    # SUPPRESS so that an option given before the subcommand is not reset by
    # the subcommand's own copy of it; defaults are filled in by main().
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--db", default=argparse.SUPPRESS,
                        help="corpus file (default: $VERA_DB, else the demo corpus)")
    common.add_argument("--with-demo", action="store_true", default=argparse.SUPPRESS,
                        help="also load the demonstration entities into the corpus file")
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="machine-readable output")

    p = argparse.ArgumentParser(
        prog="vera", parents=[common],
        description="V.E.R.A.: verify existence before predication (Wessel 1992).",
    )
    p.add_argument("--version", action="version", version=f"vera {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("check", parents=[common], help="verify a statement")
    c.add_argument("statement", nargs="+")
    c.add_argument("--audit", action="store_true", help="include the full audit trail")
    c.add_argument("--require-resolvable", action="store_true",
                   help="block a VERIFIED result unless every source can be re-read "
                        "(named-only evidence exits 1)")
    c.set_defaults(func=cmd_check)

    i = sub.add_parser("identity", parents=[common], help="identity relation between two names")
    i.add_argument("a")
    i.add_argument("b")
    i.set_defaults(func=cmd_identity)

    corpus = sub.add_parser("corpus", help="manage an E! Corpus file")
    csub = corpus.add_subparsers(dest="corpus_command", required=True)

    ci = csub.add_parser("init", parents=[common], help="create or upgrade a corpus file")
    ci.set_defaults(func=cmd_corpus_init)

    cs = csub.add_parser("stats", parents=[common], help="corpus counts")
    cs.set_defaults(func=cmd_corpus_stats)

    cl = csub.add_parser("lookup", parents=[common], help="existence of one name")
    cl.add_argument("name")
    cl.set_defaults(func=cmd_corpus_lookup)

    cq = csub.add_parser("search", parents=[common], help="substring search")
    cq.add_argument("query")
    cq.add_argument("--limit", type=int, default=20)
    cq.set_defaults(func=cmd_corpus_search)

    ca = csub.add_parser("add", parents=[common], help="add an entity with its evidence")
    ca.add_argument("name")
    ca.add_argument("--type", required=True, choices=[t.value for t in EntityType])
    ca.add_argument("--status", required=True, choices=["EXISTS", "NOT_EXISTS"])
    ca.add_argument("--url", help="resolvable source URL")
    ca.add_argument("--named-source", help="source identified by name only")
    ca.add_argument("--title", help="title of a resolvable source")
    ca.add_argument("--source-type", default="MANUAL")
    ca.add_argument("--source-date")
    ca.add_argument("--back-ref", help="where the source was found (not evidence)")
    ca.add_argument("--alias", action="append", default=[])
    ca.add_argument("--description")
    ca.add_argument("--wikidata", help="Wikidata QID")
    ca.add_argument("--confidence", type=float, default=0.9)
    ca.add_argument("--reliability", type=float, default=0.85)
    ca.set_defaults(func=cmd_corpus_add)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    for name, default in (("db", None), ("with_demo", False), ("json", False)):
        if not hasattr(args, name):
            setattr(args, name, default)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
