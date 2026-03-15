"""
V.E.R.A. E! Verification Service
==================================
Layer 2 of the Triple-Layer Verification System

Implements the E! Corpus: a SQLite-backed store of verified entity existence
facts. All existence claims in V.E.R.A. must pass through this service before
being asserted in any response.

Architecture Role:
- Implements IF-002 (E! Corpus API) from VERA_Interface_Specifications_v1_0
- Called by VERAPipeline after Layer 1 (Krampitz) confirms e-type loading
- Returns EXISTS / NOT_EXISTS / UNKNOWN with provenance for every entity

NTP Principle:
    Existence (E!) is always separate from predication (M).
    A formula may describe properties perfectly well and still refer to
    a non-existent entity. The E! Verification Service enforces this wall.

Source: Wessel, H. (1992). 'Existenz, Ununterscheidbarkeit, Identitaet.'
        Wissenschaftliche Zeitschrift der Humboldt-Universitaet zu Berlin,
        Reihe Geistes- und Sozialwiss. 41, pp. 30-39

Author: V.E.R.A. Open Source Initiative
Version: 0.1.0 (Prototype -- SQLite seed corpus)
Date: March 2026
"""

import sqlite3
import uuid
import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime


# =============================================================================
# Type Definitions
# =============================================================================

class ExistenceStatus(Enum):
    """Possible outcomes of an existence check."""
    EXISTS = "EXISTS"             # Entity is in the E! Corpus with provenance
    NOT_EXISTS = "NOT_EXISTS"     # Entity is confirmed not to exist
    UNKNOWN = "UNKNOWN"           # Entity not in corpus; existence unverifiable


class EntityType(Enum):
    """Classification of entity kinds."""
    PERSON = "PERSON"
    PLACE = "PLACE"
    SUBSTANCE = "SUBSTANCE"       # Drugs, chemicals, compounds
    ORGANISATION = "ORGANISATION"
    CONCEPT = "CONCEPT"
    BIOLOGICAL = "BIOLOGICAL"     # Species, organisms
    THING = "THING"               # General physical objects
    EVENT = "EVENT"
    FICTIONAL = "FICTIONAL"       # Known non-existent (fictional entities)


@dataclass
class Provenance:
    """Evidence record for an existence claim."""
    source_type: str              # e.g. WIKIPEDIA, WIKIDATA, WHO, NZ_FORMULARY
    source_url: str
    reliability_score: float      # 0.0 to 1.0
    retrieved_date: str           # ISO date string
    notes: Optional[str] = None


@dataclass
class ExistenceResult:
    """
    Result of an E! Corpus existence check.
    Matches IF-002 response schema exactly.
    """
    entity_name: str
    existence_status: ExistenceStatus
    confidence: float
    entity_id: Optional[str] = None
    canonical_name: Optional[str] = None
    entity_type: Optional[EntityType] = None
    provenance: Optional[Provenance] = None
    properties: List[Dict[str, Any]] = field(default_factory=list)
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        d = {
            "entity_name": self.entity_name,
            "existence_status": self.existence_status.value,
            "confidence": self.confidence,
            "entity_id": self.entity_id,
            "canonical_name": self.canonical_name,
            "entity_type": self.entity_type.value if self.entity_type else None,
            "provenance": asdict(self.provenance) if self.provenance else None,
            "properties": self.properties,
        }
        if self.error_code:
            d["error_code"] = self.error_code
            d["error_message"] = self.error_message
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


# =============================================================================
# Database Schema
# =============================================================================

SCHEMA_SQL = """
-- E! Corpus: entities table
-- Every row represents one verified (or verified-not-to-exist) entity.
CREATE TABLE IF NOT EXISTS entities (
    entity_id       TEXT PRIMARY KEY,
    canonical_name  TEXT NOT NULL,
    entity_type     TEXT NOT NULL,
    status          TEXT NOT NULL,          -- EXISTS | NOT_EXISTS
    confidence      REAL NOT NULL DEFAULT 1.0,
    created_at      TEXT NOT NULL,
    notes           TEXT
);

-- Aliases: alternative names that resolve to a canonical entity
CREATE TABLE IF NOT EXISTS aliases (
    alias_id        TEXT PRIMARY KEY,
    entity_id       TEXT NOT NULL REFERENCES entities(entity_id),
    alias_name      TEXT NOT NULL,
    alias_type      TEXT,                   -- e.g. ABBREVIATION, TRADE_NAME, SYNONYM
    UNIQUE(alias_name COLLATE NOCASE)
);

-- Provenance: one or more evidence records per entity
CREATE TABLE IF NOT EXISTS provenance (
    provenance_id   TEXT PRIMARY KEY,
    entity_id       TEXT NOT NULL REFERENCES entities(entity_id),
    source_type     TEXT NOT NULL,
    source_url      TEXT NOT NULL,
    reliability_score REAL NOT NULL DEFAULT 0.9,
    retrieved_date  TEXT NOT NULL,
    notes           TEXT
);

-- Properties: verifiable facts about existing entities
CREATE TABLE IF NOT EXISTS properties (
    property_id     TEXT PRIMARY KEY,
    entity_id       TEXT NOT NULL REFERENCES entities(entity_id),
    property_name   TEXT NOT NULL,
    property_value  TEXT NOT NULL,
    confidence      REAL NOT NULL DEFAULT 0.9,
    provenance_id   TEXT REFERENCES provenance(provenance_id)
);

-- Audit log: every existence check is recorded
CREATE TABLE IF NOT EXISTS audit_log (
    log_id          TEXT PRIMARY KEY,
    query_name      TEXT NOT NULL,
    normalised_name TEXT NOT NULL,
    result_status   TEXT NOT NULL,
    confidence      REAL,
    timestamp       TEXT NOT NULL,
    pipeline_run_id TEXT
);

-- Canonical name index
CREATE INDEX IF NOT EXISTS idx_entities_canonical ON entities(canonical_name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_aliases_name ON aliases(alias_name COLLATE NOCASE);
"""


# =============================================================================
# Seed Data: v0.1 Corpus
# =============================================================================
# Curated for the demo first query and Pharma 500 preview.
# Provenance: Wikipedia (reliability 0.85) and WHO/Wikidata (reliability 0.95).
# All entities are real, widely cited, and suitable for demonstration.

SEED_DATA = [
    # -------------------------------------------------------------------------
    # Philosophy / Classic NTP Examples
    # -------------------------------------------------------------------------
    {
        "entity_id": "ent-soc-001",
        "canonical_name": "Socrates",
        "entity_type": EntityType.PERSON,
        "status": ExistenceStatus.EXISTS,
        "confidence": 0.99,
        "notes": "Ancient Greek philosopher, ~470-399 BCE. Historical existence well-attested.",
        "aliases": [("Σωκράτης", "ORIGINAL_NAME")],
        "provenance": ("WIKIPEDIA", "https://en.wikipedia.org/wiki/Socrates", 0.90),
        "properties": [
            ("occupation", "philosopher"),
            ("nationality", "Athenian Greek"),
            ("period", "Classical antiquity"),
        ]
    },
    {
        "entity_id": "ent-ari-001",
        "canonical_name": "Aristotle",
        "entity_type": EntityType.PERSON,
        "status": ExistenceStatus.EXISTS,
        "confidence": 0.99,
        "notes": "Ancient Greek philosopher, 384-322 BCE.",
        "aliases": [("Ἀριστοτέλης", "ORIGINAL_NAME")],
        "provenance": ("WIKIPEDIA", "https://en.wikipedia.org/wiki/Aristotle", 0.90),
        "properties": [
            ("occupation", "philosopher"),
            ("nationality", "Macedonian Greek"),
            ("period", "Classical antiquity"),
        ]
    },
    # Fictional entity -- known NOT to exist. Used to test the firewall.
    {
        "entity_id": "ent-fic-001",
        "canonical_name": "Sherlock Holmes",
        "entity_type": EntityType.FICTIONAL,
        "status": ExistenceStatus.NOT_EXISTS,
        "confidence": 1.0,
        "notes": "Fictional character created by Arthur Conan Doyle. Does not exist as a real person.",
        "aliases": [("Holmes", "INFORMAL"), ("Mr Holmes", "FORMAL")],
        "provenance": ("WIKIPEDIA", "https://en.wikipedia.org/wiki/Sherlock_Holmes", 0.95),
        "properties": [
            ("creator", "Arthur Conan Doyle"),
            ("first_appearance", "A Study in Scarlet (1887)"),
            ("fictional_residence", "221B Baker Street, London"),
        ]
    },
    # -------------------------------------------------------------------------
    # Pharmaceutical -- Pharma 500 POC Preview
    # -------------------------------------------------------------------------
    {
        "entity_id": "ent-asp-001",
        "canonical_name": "Aspirin",
        "entity_type": EntityType.SUBSTANCE,
        "status": ExistenceStatus.EXISTS,
        "confidence": 1.0,
        "notes": "Acetylsalicylic acid. WHO Essential Medicine.",
        "aliases": [
            ("Acetylsalicylic acid", "CHEMICAL_NAME"),
            ("ASA", "ABBREVIATION"),
            ("2-acetoxybenzoic acid", "IUPAC"),
        ],
        "provenance": ("WHO_ESSENTIAL_MEDICINES", "https://list.essentialmedicines.who.int/", 0.99),
        "properties": [
            ("drug_class", "NSAID"),
            ("mechanism", "COX-1 and COX-2 inhibitor"),
            ("who_essential_medicine", "true"),
            ("cas_number", "50-78-2"),
        ]
    },
    {
        "entity_id": "ent-par-001",
        "canonical_name": "Paracetamol",
        "entity_type": EntityType.SUBSTANCE,
        "status": ExistenceStatus.EXISTS,
        "confidence": 1.0,
        "notes": "Acetaminophen. WHO Essential Medicine. Known as Paracetamol in NZ/UK, Acetaminophen in US.",
        "aliases": [
            ("Acetaminophen", "REGIONAL_NAME"),
            ("Tylenol", "TRADE_NAME"),
            ("Panadol", "TRADE_NAME"),
            ("APAP", "ABBREVIATION"),
            ("4-acetamidophenol", "CHEMICAL_NAME"),
        ],
        "provenance": ("WHO_ESSENTIAL_MEDICINES", "https://list.essentialmedicines.who.int/", 0.99),
        "properties": [
            ("drug_class", "Analgesic/Antipyretic"),
            ("mechanism", "COX-3 inhibitor (CNS)"),
            ("who_essential_medicine", "true"),
            ("cas_number", "103-90-2"),
        ]
    },
    {
        "entity_id": "ent-pen-001",
        "canonical_name": "Penicillin",
        "entity_type": EntityType.SUBSTANCE,
        "status": ExistenceStatus.EXISTS,
        "confidence": 1.0,
        "notes": "Group of beta-lactam antibiotics. WHO Essential Medicine.",
        "aliases": [
            ("Penicillin G", "SPECIFIC_FORM"),
            ("Benzylpenicillin", "CHEMICAL_NAME"),
            ("PCN", "ABBREVIATION"),
        ],
        "provenance": ("WHO_ESSENTIAL_MEDICINES", "https://list.essentialmedicines.who.int/", 0.99),
        "properties": [
            ("drug_class", "Beta-lactam antibiotic"),
            ("mechanism", "Cell wall synthesis inhibitor"),
            ("discoverer", "Alexander Fleming"),
            ("discovery_year", "1928"),
            ("who_essential_medicine", "true"),
        ]
    },
    {
        "entity_id": "ent-mor-001",
        "canonical_name": "Morphine",
        "entity_type": EntityType.SUBSTANCE,
        "status": ExistenceStatus.EXISTS,
        "confidence": 1.0,
        "notes": "Opioid analgesic. WHO Essential Medicine.",
        "aliases": [
            ("MS Contin", "TRADE_NAME"),
            ("Morphine sulfate", "CHEMICAL_NAME"),
        ],
        "provenance": ("WHO_ESSENTIAL_MEDICINES", "https://list.essentialmedicines.who.int/", 0.99),
        "properties": [
            ("drug_class", "Opioid analgesic"),
            ("mechanism", "Mu-opioid receptor agonist"),
            ("who_essential_medicine", "true"),
            ("controlled_substance", "true"),
        ]
    },
    # -------------------------------------------------------------------------
    # Technology -- for demo queries
    # -------------------------------------------------------------------------
    {
        "entity_id": "ent-py-001",
        "canonical_name": "Python",
        "entity_type": EntityType.THING,
        "status": ExistenceStatus.EXISTS,
        "confidence": 0.99,
        "notes": "General-purpose programming language. First released 1991.",
        "aliases": [
            ("Python programming language", "FULL_NAME"),
            ("CPython", "IMPLEMENTATION"),
        ],
        "provenance": ("WIKIPEDIA", "https://en.wikipedia.org/wiki/Python_(programming_language)", 0.90),
        "properties": [
            ("creator", "Guido van Rossum"),
            ("first_release", "1991"),
            ("paradigm", "multi-paradigm"),
        ]
    },
    # Ambiguous entity -- same name, multiple referents. Tests UNKNOWN path.
    {
        "entity_id": "ent-py-002",
        "canonical_name": "Python (snake)",
        "entity_type": EntityType.BIOLOGICAL,
        "status": ExistenceStatus.EXISTS,
        "confidence": 0.99,
        "notes": "Genus of large, non-venomous snakes.",
        "aliases": [("Python (genus)", "TAXONOMIC")],
        "provenance": ("WIKIPEDIA", "https://en.wikipedia.org/wiki/Pythonidae", 0.85),
        "properties": [
            ("taxonomy", "Family Pythonidae"),
            ("habitat", "Africa, Asia, Australia"),
        ]
    },
]


# =============================================================================
# E! Verification Service
# =============================================================================

class EVerificationService:
    """
    Layer 2: E! Corpus Verification Service.

    All entity existence claims must pass through this service.
    Returns EXISTS, NOT_EXISTS, or UNKNOWN for every entity queried.

    The separation of predication (M) from existence (E!) is enforced here:
    a formula may be grammatically correct and logically well-formed while
    still referring to a non-existent entity. This service is the gatekeeper.

    Usage:
        service = EVerificationService()
        result = service.check_existence("Aspirin")
        print(result.existence_status)  # ExistenceStatus.EXISTS
    """

    def __init__(self, db_path: str = ":memory:"):
        """
        Initialise the service with a SQLite database.

        Args:
            db_path: Path to SQLite file, or ':memory:' for in-memory (testing).
        """
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._initialise_schema()
        self._load_seed_data()

    def _initialise_schema(self) -> None:
        """Create tables if they do not exist."""
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()

    def _load_seed_data(self) -> None:
        """Populate corpus with v0.1 seed entities, skipping existing records."""
        cur = self._conn.cursor()
        now = datetime.utcnow().isoformat()

        for entity in SEED_DATA:
            # Skip if already loaded (idempotent)
            cur.execute("SELECT 1 FROM entities WHERE entity_id = ?", (entity["entity_id"],))
            if cur.fetchone():
                continue

            cur.execute(
                "INSERT INTO entities VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    entity["entity_id"],
                    entity["canonical_name"],
                    entity["entity_type"].value,
                    entity["status"].value,
                    entity["confidence"],
                    now,
                    entity.get("notes"),
                )
            )

            # Insert canonical name as its own alias for uniform lookup
            cur.execute(
                "INSERT OR IGNORE INTO aliases VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), entity["entity_id"], entity["canonical_name"], "CANONICAL")
            )

            # Insert aliases
            for alias_name, alias_type in entity.get("aliases", []):
                cur.execute(
                    "INSERT OR IGNORE INTO aliases VALUES (?, ?, ?, ?)",
                    (str(uuid.uuid4()), entity["entity_id"], alias_name, alias_type)
                )

            # Insert provenance
            source_type, source_url, reliability = entity["provenance"]
            prov_id = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO provenance VALUES (?, ?, ?, ?, ?, ?, ?)",
                (prov_id, entity["entity_id"], source_type, source_url, reliability, now, None)
            )

            # Insert properties
            for prop_name, prop_value in entity.get("properties", []):
                cur.execute(
                    "INSERT INTO properties VALUES (?, ?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), entity["entity_id"], prop_name, prop_value, entity["confidence"], prov_id)
                )

        self._conn.commit()

    # -------------------------------------------------------------------------
    # Public Interface (matches IF-002)
    # -------------------------------------------------------------------------

    def check_existence(
        self,
        entity_name: str,
        fuzzy: bool = False,
        include_aliases: bool = True,
        pipeline_run_id: Optional[str] = None,
    ) -> ExistenceResult:
        """
        Check whether an entity exists in the E! Corpus.

        Equivalent to: GET /api/v1/exists/{entity_name}

        Args:
            entity_name: Name or alias to look up.
            fuzzy: Enable fuzzy (partial) matching (not yet implemented in v0.1).
            include_aliases: Search alias table as well as canonical names.
            pipeline_run_id: Trace ID from the calling pipeline run.

        Returns:
            ExistenceResult with status EXISTS, NOT_EXISTS, or UNKNOWN.
        """
        normalised = entity_name.strip()
        entity_row = self._find_entity(normalised, include_aliases)

        if entity_row:
            prov_row = self._get_provenance(entity_row["entity_id"])
            props = self._get_properties(entity_row["entity_id"])
            status = ExistenceStatus(entity_row["status"])
            result = ExistenceResult(
                entity_name=entity_name,
                existence_status=status,
                confidence=entity_row["confidence"],
                entity_id=entity_row["entity_id"],
                canonical_name=entity_row["canonical_name"],
                entity_type=EntityType(entity_row["entity_type"]),
                provenance=Provenance(
                    source_type=prov_row["source_type"],
                    source_url=prov_row["source_url"],
                    reliability_score=prov_row["reliability_score"],
                    retrieved_date=prov_row["retrieved_date"],
                    notes=prov_row["notes"],
                ) if prov_row else None,
                properties=props,
            )
        else:
            result = ExistenceResult(
                entity_name=entity_name,
                existence_status=ExistenceStatus.UNKNOWN,
                confidence=0.0,
                error_code="VERA-001",
                error_message=f"Entity '{entity_name}' not found in E! Corpus.",
            )

        self._audit(normalised, result, pipeline_run_id)
        return result

    def get_corpus_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the E! Corpus."""
        cur = self._conn.cursor()
        stats = {}
        cur.execute("SELECT COUNT(*) FROM entities WHERE status = 'EXISTS'")
        stats["existing_entities"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM entities WHERE status = 'NOT_EXISTS'")
        stats["confirmed_nonexistent"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM aliases")
        stats["alias_records"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM properties")
        stats["property_records"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM provenance")
        stats["provenance_records"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM audit_log")
        stats["queries_logged"] = cur.fetchone()[0]
        return stats

    def add_entity(
        self,
        canonical_name: str,
        entity_type: EntityType,
        status: ExistenceStatus,
        source_type: str,
        source_url: str,
        reliability_score: float = 0.85,
        aliases: Optional[List[tuple]] = None,
        properties: Optional[List[tuple]] = None,
        confidence: float = 0.9,
        notes: Optional[str] = None,
    ) -> str:
        """
        Add a new entity to the E! Corpus programmatically.
        Used for corpus expansion (Pharma 500 build, contributor submissions).

        Returns the new entity_id.
        """
        entity_id = f"ent-{str(uuid.uuid4())[:8]}"
        now = datetime.utcnow().isoformat()
        cur = self._conn.cursor()

        cur.execute(
            "INSERT INTO entities VALUES (?, ?, ?, ?, ?, ?, ?)",
            (entity_id, canonical_name, entity_type.value, status.value, confidence, now, notes)
        )
        cur.execute(
            "INSERT OR IGNORE INTO aliases VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), entity_id, canonical_name, "CANONICAL")
        )
        for alias_name, alias_type in (aliases or []):
            cur.execute(
                "INSERT OR IGNORE INTO aliases VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), entity_id, alias_name, alias_type)
            )
        prov_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO provenance VALUES (?, ?, ?, ?, ?, ?, ?)",
            (prov_id, entity_id, source_type, source_url, reliability_score, now, None)
        )
        for prop_name, prop_value in (properties or []):
            cur.execute(
                "INSERT INTO properties VALUES (?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), entity_id, prop_name, prop_value, confidence, prov_id)
            )
        self._conn.commit()
        return entity_id

    # -------------------------------------------------------------------------
    # Private Helpers
    # -------------------------------------------------------------------------

    def _find_entity(self, name: str, include_aliases: bool) -> Optional[sqlite3.Row]:
        cur = self._conn.cursor()
        # Direct canonical match
        cur.execute(
            "SELECT * FROM entities WHERE canonical_name = ? COLLATE NOCASE", (name,)
        )
        row = cur.fetchone()
        if row:
            return row
        if include_aliases:
            cur.execute(
                """
                SELECT e.* FROM entities e
                JOIN aliases a ON e.entity_id = a.entity_id
                WHERE a.alias_name = ? COLLATE NOCASE
                """,
                (name,)
            )
            return cur.fetchone()
        return None

    def _get_provenance(self, entity_id: str) -> Optional[sqlite3.Row]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT * FROM provenance WHERE entity_id = ? ORDER BY reliability_score DESC LIMIT 1",
            (entity_id,)
        )
        return cur.fetchone()

    def _get_properties(self, entity_id: str) -> List[Dict[str, Any]]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT property_name, property_value, confidence FROM properties WHERE entity_id = ?",
            (entity_id,)
        )
        return [dict(row) for row in cur.fetchall()]

    def _audit(self, normalised_name: str, result: ExistenceResult, pipeline_run_id: Optional[str]) -> None:
        self._conn.execute(
            "INSERT INTO audit_log VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                result.entity_name,
                normalised_name,
                result.existence_status.value,
                result.confidence,
                datetime.utcnow().isoformat(),
                pipeline_run_id,
            )
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


# =============================================================================
# Test Suite
# =============================================================================

def run_test_suite() -> tuple:
    """
    Test suite for the E! Verification Service.
    Tests the EXISTS / NOT_EXISTS / UNKNOWN decision paths
    and alias resolution.
    """
    print("=" * 70)
    print("V.E.R.A. E! Verification Service - Test Suite")
    print("Implements IF-002 (VERA_Interface_Specifications_v1_0)")
    print("=" * 70)
    print()

    service = EVerificationService(db_path=":memory:")
    passed = 0
    failed = 0

    test_cases = [
        # EVS-001: Known existing entity (canonical name)
        {
            "id": "EVS-001",
            "query": "Aspirin",
            "expected_status": ExistenceStatus.EXISTS,
            "description": "Known drug by canonical name",
        },
        # EVS-002: Alias resolution -- Paracetamol known as Acetaminophen in US
        {
            "id": "EVS-002",
            "query": "Acetaminophen",
            "expected_status": ExistenceStatus.EXISTS,
            "description": "Alias lookup -- Acetaminophen resolves to Paracetamol",
        },
        # EVS-003: Trade name alias
        {
            "id": "EVS-003",
            "query": "Panadol",
            "expected_status": ExistenceStatus.EXISTS,
            "description": "Trade name alias -- Panadol resolves to Paracetamol",
        },
        # EVS-004: Known non-existent (fictional entity)
        {
            "id": "EVS-004",
            "query": "Sherlock Holmes",
            "expected_status": ExistenceStatus.NOT_EXISTS,
            "description": "Fictional entity -- should return NOT_EXISTS",
        },
        # EVS-005: Unknown entity -- not in corpus
        {
            "id": "EVS-005",
            "query": "Zarkonite",
            "expected_status": ExistenceStatus.UNKNOWN,
            "description": "Invented name -- should return UNKNOWN",
        },
        # EVS-006: Historical person
        {
            "id": "EVS-006",
            "query": "Socrates",
            "expected_status": ExistenceStatus.EXISTS,
            "description": "Historical person -- EXISTS with low confidence OK",
        },
        # EVS-007: Case-insensitive lookup
        {
            "id": "EVS-007",
            "query": "ASPIRIN",
            "expected_status": ExistenceStatus.EXISTS,
            "description": "Case-insensitive -- ASPIRIN should resolve",
        },
        # EVS-008: Chemical name alias
        {
            "id": "EVS-008",
            "query": "Acetylsalicylic acid",
            "expected_status": ExistenceStatus.EXISTS,
            "description": "Chemical name alias for Aspirin",
        },
        # EVS-009: Programming language (non-drug domain)
        {
            "id": "EVS-009",
            "query": "Python",
            "expected_status": ExistenceStatus.EXISTS,
            "description": "Technology entity -- Python programming language",
        },
        # EVS-010: Provenance is present for EXISTS results
        {
            "id": "EVS-010",
            "query": "Penicillin",
            "expected_status": ExistenceStatus.EXISTS,
            "description": "Provenance must be present for EXISTS result",
            "check_provenance": True,
        },
    ]

    for tc in test_cases:
        result = service.check_existence(tc["query"])
        status_ok = result.existence_status == tc["expected_status"]
        prov_ok = True
        if tc.get("check_provenance") and tc["expected_status"] == ExistenceStatus.EXISTS:
            prov_ok = result.provenance is not None

        ok = status_ok and prov_ok
        icon = "PASS" if ok else "FAIL"

        if ok:
            passed += 1
        else:
            failed += 1

        print(f"[{tc['id']}] {icon}")
        print(f"  Query:    '{tc['query']}'")
        print(f"  Expected: {tc['expected_status'].value}")
        print(f"  Got:      {result.existence_status.value}  (confidence: {result.confidence:.2f})")
        if result.canonical_name and result.canonical_name != tc["query"]:
            print(f"  Resolved: '{result.canonical_name}'")
        if result.existence_status == ExistenceStatus.EXISTS and result.provenance:
            print(f"  Source:   {result.provenance.source_type} (reliability: {result.provenance.reliability_score})")
        if not prov_ok:
            print(f"  ERROR: Provenance missing for EXISTS result")
        print()

    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("=" * 70)
    print()

    stats = service.get_corpus_stats()
    print("Corpus Statistics:")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    service.close()
    return passed, failed


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    print()
    print("=" * 70)
    print("  V.E.R.A. -- E! Verification Service v0.1.0")
    print("  Layer 2: Existence Verification")
    print("  'Truth is a feature, not an option.'")
    print("=" * 70)
    print()

    run_test_suite()
