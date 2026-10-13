"""
Tests for the unified E! Corpus (Layer 2) and its schema migrations.

The existence and identity cases are ported from the retired e_corpus.py
prototype's embedded suite (19 checks, all passing against that prototype
on 13 October 2026), so the merge is held to what the prototype promised.

One deliberate change from the prototype's seed: it gave Zeus the alias
"Jupiter", which would have made the planet NOT_EXISTS. It is dropped here.
"""

import sqlite3

import pytest

from vera import (
    EntityType,
    EVerificationService,
    ExistenceStatus,
    IdentityRelationType,
    ProvenanceKind,
)
from vera.corpus_schema import MIGRATIONS, SCHEMA_VERSION, SchemaVersionError, migrate

WD = "WIKIDATA"


def _add(svc, name, etype, status, url, aliases=(), **kw):
    return svc.add_entity(
        canonical_name=name,
        entity_type=etype,
        status=status,
        source_type=kw.pop("source_type", WD),
        source_url=url,
        aliases=[(a, "ALTERNATE") for a in aliases],
        confidence=kw.pop("confidence", 0.99),
        **kw,
    )


@pytest.fixture
def corpus():
    svc = EVerificationService(":memory:", seed=False)
    E, N = ExistenceStatus.EXISTS, ExistenceStatus.NOT_EXISTS
    _add(svc, "Socrates", EntityType.PERSON, E, "https://www.wikidata.org/wiki/Q913", ["Σωκράτης"])
    _add(svc, "Albert Einstein", EntityType.PERSON, E, "https://www.wikidata.org/wiki/Q937",
         ["A. Einstein", "Einstein"])
    higgs = _add(svc, "Higgs boson", EntityType.THING, E,
                 "https://www.science.org/doi/10.1126/science.1232005",
                 ["Higgs particle"], source_type="SCIENTIFIC", confidence=0.95)
    svc.add_property(higgs, "mass", "125.25", confidence=0.95)
    _add(svc, "Cygnus atratus", EntityType.BIOLOGICAL, E, "https://www.wikidata.org/wiki/Q35409",
         ["Black swan"])
    _add(svc, "Paris", EntityType.PLACE, E, "https://www.wikidata.org/wiki/Q90")
    _add(svc, "Unicorn", EntityType.FICTIONAL, N, "https://www.wikidata.org/wiki/Q19683", ["unicorns"])
    _add(svc, "Pegasus", EntityType.MYTHOLOGICAL, N, "https://www.wikidata.org/wiki/Q188651")
    _add(svc, "Sherlock Holmes", EntityType.FICTIONAL, N, "https://www.wikidata.org/wiki/Q4271",
         ["The Great Detective"])
    _add(svc, "Zeus", EntityType.MYTHOLOGICAL, N, "https://www.wikidata.org/wiki/Q34201", ["Ζεύς"])
    yield svc
    svc.close()


# -----------------------------------------------------------------------------
# Existence (ported, 13 cases)
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("name,expected", [
    ("Socrates", ExistenceStatus.EXISTS),
    ("Albert Einstein", ExistenceStatus.EXISTS),
    ("Einstein", ExistenceStatus.EXISTS),
    ("Higgs boson", ExistenceStatus.EXISTS),
    ("Black swan", ExistenceStatus.EXISTS),
    ("Paris", ExistenceStatus.EXISTS),
    ("Unicorn", ExistenceStatus.NOT_EXISTS),
    ("unicorns", ExistenceStatus.NOT_EXISTS),
    ("Pegasus", ExistenceStatus.NOT_EXISTS),
    ("Sherlock Holmes", ExistenceStatus.NOT_EXISTS),
    ("Zeus", ExistenceStatus.NOT_EXISTS),
    ("Xyzzy Foobar", ExistenceStatus.UNKNOWN),
    ("Professor Smith", ExistenceStatus.UNKNOWN),
])
def test_existence(corpus, name, expected):
    result = corpus.check_existence(name)
    assert result.existence_status is expected
    assert (result.entity_id is not None) == (expected is not ExistenceStatus.UNKNOWN)


def test_jupiter_is_not_an_alias_of_zeus(corpus):
    assert corpus.check_existence("Jupiter").existence_status is ExistenceStatus.UNKNOWN


# -----------------------------------------------------------------------------
# Identity (ported, 5 cases)
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("a,b,expected", [
    ("Albert Einstein", "A. Einstein", IdentityRelationType.SAME_AS),
    ("Albert Einstein", "Einstein", IdentityRelationType.SAME_AS),
    ("Socrates", "Albert Einstein", IdentityRelationType.DIFFERENT),
    # D3 requires E!(x) and E!(y); both NOT_EXISTS, so it cannot apply.
    ("Unicorn", "Pegasus", IdentityRelationType.UNKNOWN),
    ("Unknown Person A", "Unknown Person B", IdentityRelationType.UNKNOWN),
])
def test_identity(corpus, a, b, expected):
    assert corpus.resolve_identity(a, b).relation_type is expected


def test_stored_identity_relation_wins_over_inference(corpus):
    a = corpus.check_existence("Socrates").entity_id
    b = corpus.check_existence("Albert Einstein").entity_id
    corpus.add_identity_relation(a, b, IdentityRelationType.WEAK_INDISCERNIBLE, 0.4)
    r = corpus.resolve_identity("Einstein", "Socrates")
    assert r.relation_type is IdentityRelationType.WEAK_INDISCERNIBLE
    assert r.ntp_relation == "~(x#y)"


# -----------------------------------------------------------------------------
# Properties (ported, 1 case)
# -----------------------------------------------------------------------------

def test_property_retrieval(corpus):
    props = corpus.check_existence("Higgs boson").properties
    assert {"property_name": "mass", "property_value": "125.25", "confidence": 0.95} in props


# -----------------------------------------------------------------------------
# Provenance kinds and back-references
# -----------------------------------------------------------------------------

def test_named_source_needs_a_title(corpus):
    with pytest.raises(ValueError, match="source_title"):
        corpus.add_entity("DPMC", EntityType.ORGANISATION, ExistenceStatus.EXISTS,
                          source_type="GOVERNMENT", provenance_kind=ProvenanceKind.NAMED)


def test_resolvable_source_needs_a_url(corpus):
    with pytest.raises(ValueError, match="source_url"):
        corpus.add_entity("DPMC", EntityType.ORGANISATION, ExistenceStatus.EXISTS,
                          source_type="GOVERNMENT")


def test_named_source_is_stored_and_reported_as_named(corpus):
    corpus.add_entity(
        "Department of the Prime Minister and Cabinet", EntityType.ORGANISATION,
        ExistenceStatus.EXISTS, source_type="GOVERNMENT",
        provenance_kind=ProvenanceKind.NAMED,
        source_title="DPMC Critical Infrastructure Consultation",
        source_date="2026-02",
        back_reference="Cyber Sun Part 10",
        aliases=[("DPMC", "ABBREVIATION")],
    )
    r = corpus.check_existence("DPMC")
    assert r.existence_status is ExistenceStatus.EXISTS
    assert r.provenance.provenance_kind == "named"
    assert r.provenance.source_url is None
    assert r.provenance.back_reference == "Cyber Sun Part 10"
    stats = corpus.get_corpus_stats()
    assert stats["provenance_named"] == 1


def test_database_refuses_resolvable_row_without_url(corpus):
    """The CHECK constraint holds even if a caller bypasses add_entity."""
    eid = corpus.check_existence("Paris").entity_id
    with pytest.raises(sqlite3.IntegrityError):
        corpus._conn.execute(
            "INSERT INTO provenance (provenance_id, entity_id, source_type, "
            "reliability_score, retrieved_date, provenance_kind) "
            "VALUES ('p-x', ?, 'NEWS', 0.5, '2026-10-13', 'resolvable')",
            (eid,),
        )


def test_duplicate_name_refused(corpus):
    with pytest.raises(ValueError, match="already in the corpus"):
        _add(corpus, "einstein", EntityType.PERSON, ExistenceStatus.EXISTS, "https://x.example")


def test_seed_is_optional():
    empty = EVerificationService(":memory:", seed=False)
    assert empty.get_corpus_stats()["existing_entities"] == 0
    demo = EVerificationService(":memory:")
    assert demo.get_corpus_stats()["existing_entities"] == 8


# -----------------------------------------------------------------------------
# Migrations
# -----------------------------------------------------------------------------

def _v01_file(path):
    """A corpus file exactly as v0.1 wrote it: migration 1, user_version never set."""
    conn = sqlite3.connect(path)
    conn.executescript(MIGRATIONS[0])
    conn.execute("INSERT INTO entities VALUES ('ent-a', 'Aspirin', 'SUBSTANCE', 'EXISTS', 1.0, "
                 "'2026-03-01', NULL)")
    conn.execute("INSERT INTO aliases VALUES ('al-a', 'ent-a', 'ASA', 'ABBREVIATION')")
    conn.execute("INSERT INTO provenance VALUES ('pr-a', 'ent-a', 'WHO', "
                 "'https://list.essentialmedicines.who.int/', 0.99, '2026-03-01', NULL)")
    conn.execute("INSERT INTO properties VALUES ('pp-a', 'ent-a', 'drug_class', 'NSAID', 0.9, 'pr-a')")
    conn.commit()
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 0
    conn.close()


def test_v01_file_is_upgraded_in_place(tmp_path):
    db = tmp_path / "old.db"
    _v01_file(db)
    svc = EVerificationService(str(db), seed=False)
    assert svc.migrations_applied == [2]
    r = svc.check_existence("ASA")
    assert r.existence_status is ExistenceStatus.EXISTS
    assert r.provenance.provenance_kind == "resolvable"
    assert r.provenance.source_url == "https://list.essentialmedicines.who.int/"
    assert {"property_name": "drug_class", "property_value": "NSAID", "confidence": 0.9} in r.properties
    svc.close()
    conn = sqlite3.connect(db)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_v01_row_with_empty_url_becomes_named(tmp_path):
    db = tmp_path / "old.db"
    _v01_file(db)
    conn = sqlite3.connect(db)
    conn.execute("UPDATE provenance SET source_url = '' WHERE provenance_id = 'pr-a'")
    conn.commit()
    conn.close()
    svc = EVerificationService(str(db), seed=False)
    p = svc.check_existence("Aspirin").provenance
    assert p.provenance_kind == "named"
    assert p.source_url is None
    assert p.source_title == "WHO"


def test_reopen_applies_nothing(tmp_path):
    db = str(tmp_path / "c.db")
    first = EVerificationService(db, seed=False)
    assert first.migrations_applied == [1, 2]
    first.close()
    second = EVerificationService(db, seed=False)
    assert second.migrations_applied == []


def test_corpus_persists_across_opens(tmp_path):
    db = str(tmp_path / "c.db")
    svc = EVerificationService(db, seed=False)
    _add(svc, "Wainuiomata", EntityType.PLACE, ExistenceStatus.EXISTS,
         "https://www.wikidata.org/wiki/Q2004627")
    svc.close()
    assert EVerificationService(db, seed=False).check_existence("Wainuiomata").existence_status \
        is ExistenceStatus.EXISTS


def test_newer_schema_is_refused(tmp_path):
    db = tmp_path / "future.db"
    conn = sqlite3.connect(db)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    conn.commit()
    conn.close()
    with pytest.raises(SchemaVersionError):
        EVerificationService(str(db))


def test_failed_migration_leaves_version_unchanged():
    conn = sqlite3.connect(":memory:")
    conn.executescript(MIGRATIONS[0])
    conn.execute("PRAGMA user_version = 1")
    # Pre-create a column migration 2 adds, so its ALTER fails part-way.
    conn.execute("ALTER TABLE entities ADD COLUMN wikidata_qid TEXT")
    with pytest.raises(sqlite3.OperationalError):
        migrate(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
    cols = [r[1] for r in conn.execute("PRAGMA table_info(entities)")]
    assert "description" not in cols, "partial migration was not rolled back"
