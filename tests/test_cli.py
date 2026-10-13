"""Tests for the `vera` command line."""

import json

import pytest

from vera.cli import EXIT_ALLOWED, EXIT_BLOCKED, EXIT_NOT_EVALUATED, main


@pytest.fixture(autouse=True)
def no_env_db(monkeypatch):
    monkeypatch.delenv("VERA_DB", raising=False)


@pytest.mark.parametrize("statement,code", [
    ("Aspirin is an analgesic.", EXIT_ALLOWED),
    ("All swans are white.", EXIT_ALLOWED),
    ("Zarkonite is a rare mineral.", EXIT_BLOCKED),
    ("Sherlock Holmes is a detective.", EXIT_BLOCKED),
    ("???", EXIT_NOT_EVALUATED),
])
def test_check_exit_codes(statement, code, capsys):
    assert main(["check", statement]) == code
    assert "demonstration corpus" in capsys.readouterr().err


def test_check_json(capsys):
    main(["check", "Aspirin is an analgesic.", "--json"])
    d = json.loads(capsys.readouterr().out)
    assert d["outcome"] == "VERIFIED"
    assert d["exit_code"] == 0
    assert "audit_trail" not in d


def test_check_json_audit(capsys):
    main(["check", "Aspirin is an analgesic.", "--json", "--audit"])
    assert json.loads(capsys.readouterr().out)["audit_trail"]


def test_missing_corpus_file_is_refused(tmp_path):
    with pytest.raises(SystemExit, match="no corpus"):
        main(["--db", str(tmp_path / "absent.db"), "check", "Aspirin is an analgesic."])


def test_add_needs_a_file():
    with pytest.raises(SystemExit, match="needs a corpus file"):
        main(["corpus", "add", "X", "--type", "THING", "--status", "EXISTS", "--url", "https://x"])


def test_add_needs_exactly_one_source(tmp_path):
    db = str(tmp_path / "c.db")
    main(["--db", db, "corpus", "init"])
    with pytest.raises(SystemExit, match="exactly one"):
        main(["--db", db, "corpus", "add", "X", "--type", "THING", "--status", "EXISTS"])
    with pytest.raises(SystemExit, match="exactly one"):
        main(["--db", db, "corpus", "add", "X", "--type", "THING", "--status", "EXISTS",
              "--url", "https://x", "--named-source", "Y"])


def test_own_corpus_round_trip(tmp_path, capsys, monkeypatch):
    db = str(tmp_path / "c.db")
    assert main(["--db", db, "corpus", "init"]) == 0
    assert main(["--db", db, "corpus", "add", "DPMC", "--type", "ORGANISATION",
                 "--status", "EXISTS", "--named-source", "DPMC Critical Infrastructure Consultation",
                 "--back-ref", "Cyber Sun Part 10"]) == 0
    capsys.readouterr()

    # option after the subcommand, and via the environment
    assert main(["corpus", "lookup", "DPMC", "--db", db, "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["provenance"]["provenance_kind"] == "named"
    assert d["provenance"]["back_reference"] == "Cyber Sun Part 10"

    monkeypatch.setenv("VERA_DB", db)
    assert main(["check", "DPMC is a department."]) == EXIT_ALLOWED
    # Own corpus does not contain the demo entities unless asked.
    assert main(["check", "Aspirin is an analgesic."]) == EXIT_BLOCKED


def test_init_is_idempotent(tmp_path, capsys):
    db = str(tmp_path / "c.db")
    main(["--db", db, "corpus", "init"])
    main(["--db", db, "corpus", "init"])
    assert "already current" in capsys.readouterr().out


def test_stats_json_names_provenance_split(tmp_path, capsys):
    db = str(tmp_path / "c.db")
    main(["--db", db, "corpus", "init"])
    capsys.readouterr()
    main(["--db", db, "corpus", "stats", "--json"])
    stats = json.loads(capsys.readouterr().out)
    assert {"provenance_named", "provenance_resolvable", "schema_version"} <= stats.keys()
