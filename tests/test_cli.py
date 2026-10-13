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


def _named_corpus(tmp_path):
    db = str(tmp_path / "n.db")
    main(["--db", db, "corpus", "init"])
    main(["--db", db, "corpus", "add", "DPMC", "--type", "ORGANISATION", "--status", "EXISTS",
          "--named-source", "DPMC Critical Infrastructure Consultation"])
    main(["--db", db, "corpus", "add", "Wainuiomata", "--type", "PLACE", "--status", "EXISTS",
          "--url", "https://en.wikipedia.org/wiki/Wainuiomata"])
    return db


def test_named_evidence_is_not_called_confirmed(tmp_path, capsys):
    db = _named_corpus(tmp_path)
    capsys.readouterr()
    assert main(["--db", db, "check", "DPMC is a department.", "--json"]) == EXIT_ALLOWED
    d = json.loads(capsys.readouterr().out)
    assert d["outcome"] == "VERIFIED"
    assert d["evidence_basis"] == "named"
    assert d["named_only_subjects"] == ["DPMC"]
    assert "confirmed to exist" not in d["summary"]
    assert "attested" in d["summary"]


def test_resolvable_evidence_keeps_confirmed_wording(tmp_path, capsys):
    db = _named_corpus(tmp_path)
    capsys.readouterr()
    main(["--db", db, "check", "Wainuiomata is a valley.", "--json"])
    d = json.loads(capsys.readouterr().out)
    assert d["evidence_basis"] == "resolvable"
    assert "confirmed to exist" in d["summary"]


def test_require_resolvable_blocks_named_only(tmp_path, capsys):
    db = _named_corpus(tmp_path)
    assert main(["--db", db, "check", "DPMC is a department.", "--require-resolvable"]) \
        == EXIT_BLOCKED
    assert "held: --require-resolvable" in capsys.readouterr().out
    assert main(["--db", db, "check", "Wainuiomata is a valley.", "--require-resolvable"]) \
        == EXIT_ALLOWED


def test_import_commands(tmp_path, capsys):
    from tests.test_importers import ARTICLE, REGISTER
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "Cyber_Sunday_X_2026-06-07.md").write_text(ARTICLE, encoding="utf-8")
    (tmp_path / "src" / "draft.md").write_text('[1] Z. "Z." 2026. https://z.example/z', encoding="utf-8")
    reg = tmp_path / "reg.md"
    reg.write_text(REGISTER, encoding="utf-8")
    db = str(tmp_path / "c.db")
    main(["--db", db, "corpus", "init"])
    rep = tmp_path / "rep.json"
    assert main(["--db", db, "import", "citations", str(tmp_path / "src"),
                 "--include", r"_20\d\d-\d\d-\d\d\.md$", "--report", str(rep)]) == 0
    d = json.loads(rep.read_text())
    assert d["files"] == 1 and d["parsed"] == 4 and len(d["refusals"]) == 3
    assert all({"reason", "file", "line", "text"} <= r.keys() for r in d["refusals"])
    assert main(["--db", db, "import", "table", str(reg), "--name-column", "Reference",
                 "--origin", "register_reference"]) == 0
    assert main(["--db", db, "import", "table", str(reg), "--name-column", "Nope",
                 "--origin", "x"]) == 1
    capsys.readouterr()
    main(["--db", db, "candidates", "list", "--status", "promoted", "--json"])
    assert [c["name"] for c in json.loads(capsys.readouterr().out)] == ["Kordia"]


def test_import_needs_matching_files(tmp_path):
    db = str(tmp_path / "c.db")
    main(["--db", db, "corpus", "init"])
    with pytest.raises(SystemExit, match="no Markdown files matched"):
        main(["--db", db, "import", "citations", str(tmp_path), "--include", "nothing"])
