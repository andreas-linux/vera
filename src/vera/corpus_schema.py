"""
V.E.R.A. E! Corpus schema and migrations
=========================================

The single definition of the E! Corpus database. Every store that opens a
corpus file goes through ``migrate()``, so a file written by an older
version is brought forward in place and a file written by a newer version
is refused rather than misread.

The schema version is held in SQLite's ``PRAGMA user_version``.

Migration history
-----------------
1. The v0.1 schema from ``e_verification_service`` (entities, aliases,
   provenance, properties, audit_log). Unchanged, so corpus files created
   by v0.1 open without conversion.
2. Merges in what the separate ``e_corpus`` prototype had and v0.1 lacked:
   ``identity_relations`` (Wessel 1992, D1 to D4), entity description,
   Wikidata QID and update time, and the richer provenance record. It also
   adds ``provenance_kind``:

   * ``resolvable``: the source can be fetched again (it carries a URL).
   * ``named``: the source is identified by name only, for example
     "DPMC Critical Infrastructure Consultation, Feb 2026". It is evidence
     that a source was cited, not evidence that anyone can re-read it.

   and ``back_reference``: where the source was found (an article, say).
   A back-reference is never evidence in its own right.
3. ``candidates``: names that something suggests may be entities (a row in
   a usage register, a citation whose link reaches only a front page) but
   that no resolvable source yet backs. A candidate is never an existence
   claim; ``check_existence`` does not read this table. It is promoted to
   an entity when evidence arrives, or rejected.

Licence: GPL-3.0-or-later
"""

from __future__ import annotations

import sqlite3
from typing import List

# -----------------------------------------------------------------------------
# Migrations. Append only. Never edit a migration that has shipped.
# -----------------------------------------------------------------------------

_MIGRATION_1 = """
CREATE TABLE IF NOT EXISTS entities (
    entity_id       TEXT PRIMARY KEY,
    canonical_name  TEXT NOT NULL,
    entity_type     TEXT NOT NULL,
    status          TEXT NOT NULL,
    confidence      REAL NOT NULL DEFAULT 1.0,
    created_at      TEXT NOT NULL,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS aliases (
    alias_id        TEXT PRIMARY KEY,
    entity_id       TEXT NOT NULL REFERENCES entities(entity_id),
    alias_name      TEXT NOT NULL,
    alias_type      TEXT,
    UNIQUE(alias_name COLLATE NOCASE)
);

CREATE TABLE IF NOT EXISTS provenance (
    provenance_id   TEXT PRIMARY KEY,
    entity_id       TEXT NOT NULL REFERENCES entities(entity_id),
    source_type     TEXT NOT NULL,
    source_url      TEXT NOT NULL,
    reliability_score REAL NOT NULL DEFAULT 0.9,
    retrieved_date  TEXT NOT NULL,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS properties (
    property_id     TEXT PRIMARY KEY,
    entity_id       TEXT NOT NULL REFERENCES entities(entity_id),
    property_name   TEXT NOT NULL,
    property_value  TEXT NOT NULL,
    confidence      REAL NOT NULL DEFAULT 0.9,
    provenance_id   TEXT REFERENCES provenance(provenance_id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    log_id          TEXT PRIMARY KEY,
    query_name      TEXT NOT NULL,
    normalised_name TEXT NOT NULL,
    result_status   TEXT NOT NULL,
    confidence      REAL,
    timestamp       TEXT NOT NULL,
    pipeline_run_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_entities_canonical ON entities(canonical_name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_aliases_name ON aliases(alias_name COLLATE NOCASE);
"""

_MIGRATION_2 = """
ALTER TABLE entities ADD COLUMN description TEXT;
ALTER TABLE entities ADD COLUMN wikidata_qid TEXT;
ALTER TABLE entities ADD COLUMN updated_at TEXT;
UPDATE entities SET updated_at = created_at WHERE updated_at IS NULL;

CREATE TABLE provenance_v2 (
    provenance_id       TEXT PRIMARY KEY,
    entity_id           TEXT NOT NULL REFERENCES entities(entity_id),
    source_type         TEXT NOT NULL,
    source_url          TEXT,
    source_title        TEXT,
    source_date         TEXT,
    reliability_score   REAL NOT NULL DEFAULT 0.9
                        CHECK (reliability_score >= 0 AND reliability_score <= 1),
    retrieved_date      TEXT NOT NULL,
    verification_method TEXT NOT NULL DEFAULT 'AUTOMATED'
                        CHECK (verification_method IN ('AUTOMATED', 'MANUAL', 'HYBRID')),
    provenance_kind     TEXT NOT NULL DEFAULT 'resolvable'
                        CHECK (provenance_kind IN ('named', 'resolvable')),
    evidence_snippet    TEXT,
    back_reference      TEXT,
    notes               TEXT,
    -- A resolvable source must carry something to resolve; a named one
    -- must carry a name. Neither may be empty.
    CHECK (provenance_kind = 'named'
           OR (source_url IS NOT NULL AND source_url <> '')),
    CHECK (provenance_kind = 'resolvable'
           OR (source_title IS NOT NULL AND source_title <> ''))
);

INSERT INTO provenance_v2
    (provenance_id, entity_id, source_type, source_url, source_title,
     reliability_score, retrieved_date, provenance_kind, notes)
SELECT provenance_id, entity_id, source_type,
       NULLIF(source_url, ''),
       CASE WHEN source_url IS NULL OR source_url = '' THEN source_type END,
       reliability_score, retrieved_date,
       CASE WHEN source_url IS NULL OR source_url = '' THEN 'named' ELSE 'resolvable' END,
       notes
FROM provenance;

DROP TABLE provenance;
ALTER TABLE provenance_v2 RENAME TO provenance;

CREATE INDEX IF NOT EXISTS idx_provenance_entity ON provenance(entity_id);
CREATE INDEX IF NOT EXISTS idx_provenance_kind ON provenance(provenance_kind);
CREATE INDEX IF NOT EXISTS idx_properties_entity ON properties(entity_id);
CREATE INDEX IF NOT EXISTS idx_entities_wikidata ON entities(wikidata_qid);

CREATE TABLE IF NOT EXISTS identity_relations (
    relation_id     TEXT PRIMARY KEY,
    entity_a_id     TEXT NOT NULL REFERENCES entities(entity_id),
    entity_b_id     TEXT NOT NULL REFERENCES entities(entity_id),
    relation_type   TEXT NOT NULL CHECK (relation_type IN
        ('SAME_AS', 'DIFFERENT', 'WEAK_INDISCERNIBLE', 'STRONG_INDISCERNIBLE', 'UNKNOWN')),
    ntp_symbol      TEXT NOT NULL,
    confidence      REAL NOT NULL DEFAULT 0.5
                    CHECK (confidence >= 0 AND confidence <= 1),
    provenance_id   TEXT REFERENCES provenance(provenance_id),
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_identity_pair ON identity_relations(entity_a_id, entity_b_id);
"""

_MIGRATION_3 = """
CREATE TABLE IF NOT EXISTS candidates (
    candidate_id    TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    type_hint       TEXT,
    origin          TEXT NOT NULL,
    back_reference  TEXT,
    raw             TEXT,
    status          TEXT NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open', 'promoted', 'rejected')),
    entity_id       TEXT REFERENCES entities(entity_id),
    note            TEXT,
    created_at      TEXT NOT NULL,
    UNIQUE (name COLLATE NOCASE, origin, back_reference)
);
CREATE INDEX IF NOT EXISTS idx_candidates_name ON candidates(name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_candidates_status ON candidates(status);
CREATE INDEX IF NOT EXISTS idx_provenance_url ON provenance(source_url);
"""

MIGRATIONS: List[str] = [_MIGRATION_1, _MIGRATION_2, _MIGRATION_3]

SCHEMA_VERSION = len(MIGRATIONS)


class SchemaVersionError(RuntimeError):
    """The corpus file was written by a newer V.E.R.A. than this one."""


def current_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def _is_unversioned_v1(conn: sqlite3.Connection) -> bool:
    """A v0.1 file has the tables but never set user_version."""
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'entities'"
    ).fetchone()
    return row is not None


def migrate(conn: sqlite3.Connection) -> List[int]:
    """
    Bring ``conn`` up to SCHEMA_VERSION. Returns the migrations applied.

    Each migration runs in its own transaction with foreign keys suspended,
    because migration 2 rebuilds a table other tables reference. Foreign
    keys are re-enabled and checked afterwards; a violation fails the
    migration rather than leaving a corpus with dangling references.
    """
    version = current_version(conn)
    if version == 0 and _is_unversioned_v1(conn):
        conn.execute("PRAGMA user_version = 1")
        version = 1
    if version > SCHEMA_VERSION:
        raise SchemaVersionError(
            f"Corpus schema is version {version}; this V.E.R.A. understands "
            f"up to {SCHEMA_VERSION}. Upgrade the package rather than open it."
        )

    applied: List[int] = []
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        for number in range(version + 1, SCHEMA_VERSION + 1):
            script = MIGRATIONS[number - 1]
            conn.executescript(
                "BEGIN;\n" + script + f"\nPRAGMA user_version = {number};\nCOMMIT;"
            )
            violations = conn.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                raise sqlite3.IntegrityError(
                    f"Migration {number} left {len(violations)} foreign key violation(s)"
                )
            applied.append(number)
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
    return applied
