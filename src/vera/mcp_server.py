"""
V.E.R.A. as an MCP server
=========================

Lets an MCP client (Claude, for one) check a statement or a name against an
E! Corpus before asserting it. Read-only: no tool adds to or changes the
corpus, except that ``check_existence`` and ``check_statement`` are recorded
in the corpus's audit log, as every lookup is.

Run it over stdio:

    pip install "vera-ntp[mcp]"
    VERA_DB=/path/to/corpus.db vera-mcp
    vera-mcp --db /path/to/corpus.db

Without a corpus file it serves the built-in demonstration corpus, and every
result says ``"corpus": "demo"`` so a caller cannot mistake it for real data.

Tools
-----
check_statement   full pipeline: parse, existential loading, E! lookups
check_existence   one name: EXISTS / NOT_EXISTS / UNKNOWN, with provenance
resolve_identity  identity relation between two names (Wessel 1992, D1 to D4)
search_corpus     substring search over names and aliases
corpus_stats      counts, including the named/resolvable provenance split

Licence: GPL-3.0-or-later
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from . import __version__
from .vera_pipeline import VERAPipeline, VerificationOutcome

INSTRUCTIONS = (
    "V.E.R.A. checks whether the things a statement talks about exist, using an "
    "E! Corpus with provenance. Before asserting a property of a named entity, "
    "call check_statement or check_existence. Treat UNKNOWN as 'not established', "
    "not as 'false'. A VERIFIED result with evidence_basis 'named' means the source "
    "is identified but cannot be re-read; say so rather than calling it confirmed."
)


class VeraTools:
    """The tool logic, independent of any MCP library, so it can be tested directly."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path and not Path(db_path).exists():
            raise FileNotFoundError(f"no corpus at {db_path}; create one with "
                                    f"`vera --db {db_path} corpus init`")
        self.corpus = db_path or "demo"
        self.pipeline = VERAPipeline(db_path=db_path or ":memory:", seed=not db_path)
        self.svc = self.pipeline.e_service

    def _tag(self, d: Dict[str, Any]) -> Dict[str, Any]:
        d["corpus"] = self.corpus
        return d

    def check_statement(self, statement: str, require_resolvable: bool = False,
                        include_audit: bool = False) -> Dict[str, Any]:
        r = self.pipeline.run(statement)
        d = r.to_dict()
        if not include_audit:
            d.pop("audit_trail", None)
        allowed = r.outcome in (VerificationOutcome.VERIFIED, VerificationOutcome.NO_CHECK_REQUIRED)
        if require_resolvable and r.outcome is VerificationOutcome.VERIFIED \
                and r.evidence_basis != "resolvable":
            allowed = False
            d["held_on_named_evidence"] = True
        d["allowed"] = allowed
        return self._tag(d)

    def check_existence(self, name: str) -> Dict[str, Any]:
        return self._tag(self.svc.check_existence(name).to_dict())

    def resolve_identity(self, name_a: str, name_b: str) -> Dict[str, Any]:
        return self._tag(self.svc.resolve_identity(name_a, name_b).to_dict())

    def search_corpus(self, query: str, limit: int = 10) -> Dict[str, Any]:
        limit = max(1, min(int(limit), 50))
        return self._tag({"query": query,
                          "results": [r.to_dict() for r in self.svc.search_entities(query, limit)]})

    def corpus_stats(self) -> Dict[str, Any]:
        return self._tag(self.svc.get_corpus_stats())

    def close(self) -> None:
        self.pipeline.close()


def build_server(tools: VeraTools):
    """Register the tools on an MCP server (mcp 2.x MCPServer, or 1.x FastMCP)."""
    try:
        from mcp.server.mcpserver import MCPServer as Server
    except ImportError:
        try:
            from mcp.server.fastmcp import FastMCP as Server
        except ImportError as exc:
            raise SystemExit('vera-mcp needs the MCP SDK: pip install "vera-ntp[mcp]"') from exc

    server = Server(name="vera", instructions=INSTRUCTIONS)

    @server.tool()
    def check_statement(statement: str, require_resolvable: bool = False) -> dict:
        """Verify a statement: parse it, decide whether it presupposes existence,
        and check every subject in the E! Corpus. Returns outcome, evidence_basis,
        per-subject existence with provenance, and allowed (true/false)."""
        return tools.check_statement(statement, require_resolvable)

    @server.tool()
    def check_existence(name: str) -> dict:
        """Look up one name or alias: EXISTS, NOT_EXISTS or UNKNOWN, with provenance."""
        return tools.check_existence(name)

    @server.tool()
    def resolve_identity(name_a: str, name_b: str) -> dict:
        """Identity relation between two names (same, different, indiscernible, unknown)."""
        return tools.resolve_identity(name_a, name_b)

    @server.tool()
    def search_corpus(query: str, limit: int = 10) -> dict:
        """Substring search over canonical names and aliases (at most 50 results)."""
        return tools.search_corpus(query, limit)

    @server.tool()
    def corpus_stats() -> dict:
        """Corpus counts, including how much evidence is resolvable versus named only."""
        return tools.corpus_stats()

    return server


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="vera-mcp", description="V.E.R.A. MCP server (stdio)")
    p.add_argument("--db", default=os.environ.get("VERA_DB"),
                   help="corpus file (default: $VERA_DB, else the demo corpus)")
    p.add_argument("--version", action="version", version=f"vera-mcp {__version__}")
    args = p.parse_args(argv)
    try:
        tools = VeraTools(args.db)
    except FileNotFoundError as exc:
        print(f"vera-mcp: {exc}", file=sys.stderr)
        return 2
    if tools.corpus == "demo":
        print("vera-mcp: serving the built-in demonstration corpus (no --db or VERA_DB)",
              file=sys.stderr)
    build_server(tools).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
