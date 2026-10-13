"""Tests for the MCP server: the tool logic directly, then one real stdio round trip."""

import asyncio
import json
import os
import sys

import pytest

from vera.cli import main as cli_main
from vera.mcp_server import VeraTools


@pytest.fixture
def demo():
    t = VeraTools()
    yield t
    t.close()


def test_demo_results_are_labelled(demo):
    assert demo.check_existence("Aspirin")["corpus"] == "demo"
    assert demo.corpus_stats()["corpus"] == "demo"


def test_check_statement(demo):
    ok = demo.check_statement("Aspirin is an analgesic.")
    assert ok["outcome"] == "VERIFIED" and ok["allowed"] is True
    assert "audit_trail" not in ok
    no = demo.check_statement("Zarkonite is a rare mineral.")
    assert no["outcome"] == "REFUSAL" and no["allowed"] is False


def test_require_resolvable_holds_named_evidence(tmp_path):
    db = str(tmp_path / "c.db")
    cli_main(["--db", db, "corpus", "init"])
    cli_main(["--db", db, "corpus", "add", "DPMC", "--type", "ORGANISATION", "--status",
              "EXISTS", "--named-source", "DPMC consultation"])
    t = VeraTools(db)
    assert t.check_statement("DPMC is a department.")["allowed"] is True
    held = t.check_statement("DPMC is a department.", require_resolvable=True)
    assert held["allowed"] is False and held["held_on_named_evidence"] is True
    assert held["corpus"] == db
    t.close()


def test_missing_corpus_is_refused(tmp_path):
    with pytest.raises(FileNotFoundError):
        VeraTools(str(tmp_path / "absent.db"))


def test_search_limit_is_capped(demo):
    assert len(demo.search_corpus("a", limit=10_000)["results"]) <= 50


def test_stdio_round_trip():
    mcp = pytest.importorskip("mcp")
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def run():
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "vera.mcp_server"],
            env={k: v for k, v in os.environ.items() if k != "VERA_DB"})
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                names = {t.name for t in (await session.list_tools()).tools}
                result = await session.call_tool("check_statement",
                                                 {"statement": "Socrates is mortal."})
                return names, result

    names, result = asyncio.run(asyncio.wait_for(run(), timeout=60))
    assert names == {"check_statement", "check_existence", "resolve_identity",
                     "search_corpus", "corpus_stats"}
    payload = getattr(result, "structured_content", None) or getattr(result, "structuredContent", None)
    if payload is None:
        payload = json.loads(result.content[0].text)
    payload = payload.get("result", payload)
    assert payload["outcome"] == "VERIFIED" and payload["corpus"] == "demo"
