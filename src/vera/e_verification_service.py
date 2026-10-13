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
Version: 0.2.0 (unified E! Corpus schema, see corpus_schema.py)
Date: October 2026
"""

import sqlite3
import uuid
import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime, timezone

from .corpus_schema import SCHEMA_VERSION, migrate


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
    MYTHOLOGICAL = "MYTHOLOGICAL" # Known non-existent (mythological entities)


class ProvenanceKind(Enum):
    """
    Whether a source can be re-read, or is only identified by name.

    RESOLVABLE: carries a URL (or other locator) that can be fetched again.
    NAMED: identified by name only, e.g. "DPMC consultation, Feb 2026".
           Evidence that a source was cited, not that anyone can re-read it.
    """
    RESOLVABLE = "resolvable"
    NAMED = "named"


class IdentityRelationType(Enum):
    """
    NTP identity relations (Wessel 1992, D1 to D4).
    """
    SAME_AS = "SAME_AS"                            # x = y
    DIFFERENT = "DIFFERENT"                        # x ≠ y (D3)
    WEAK_INDISCERNIBLE = "WEAK_INDISCERNIBLE"      # ~(x#y) (D2)
    STRONG_INDISCERNIBLE = "STRONG_INDISCERNIBLE"  # ~(x ≠ y) (D4)
    UNKNOWN = "UNKNOWN"


NTP_SYMBOLS = {
    IdentityRelationType.SAME_AS: "x = y",
    IdentityRelationType.DIFFERENT: "x ≠ y",
    IdentityRelationType.WEAK_INDISCERNIBLE: "~(x#y)",
    IdentityRelationType.STRONG_INDISCERNIBLE: "~(x ≠ y)",
    IdentityRelationType.UNKNOWN: "?",
}


@dataclass
class Provenance:
    """Evidence record for an existence claim."""
    source_type: str              # e.g. WIKIPEDIA, WIKIDATA, WHO, NZ_FORMULARY
    source_url: Optional[str]     # None for a NAMED source
    reliability_score: float      # 0.0 to 1.0
    retrieved_date: str           # ISO date string
    notes: Optional[str] = None
    provenance_kind: str = ProvenanceKind.RESOLVABLE.value
    source_title: Optional[str] = None
    source_date: Optional[str] = None
    back_reference: Optional[str] = None   # where the source was found; never evidence


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


@dataclass
class IdentityResult:
    """Result of an identity resolution between two names."""
    entity_a: str
    entity_b: str
    relation_type: IdentityRelationType
    ntp_relation: str
    confidence: float
    both_exist: bool
    entity_a_id: Optional[str]
    entity_b_id: Optional[str]

    def to_dict(self) -> dict:
        return {
            "entity_a": self.entity_a,
            "entity_b": self.entity_b,
            "relation_type": self.relation_type.value,
            "ntp_relation": self.ntp_relation,
            "confidence": self.confidence,
            "both_exist": self.both_exist,
            "entity_a_id": self.entity_a_id,
            "entity_b_id": self.entity_b_id,
        }


# The schema lives in corpus_schema.py (MIGRATIONS). One definition, versioned.


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
        service = EVerificationService()                     # in-memory, demo seed
        service = EVerificationService("corpus.db", seed=False)  # your own corpus
        result = service.check_existence("Aspirin")
        print(result.existence_status)  # ExistenceStatus.EXISTS
    """

    def __init__(self, db_path: str = ":memory:", seed: bool = True):
        """
        Open (or create) an E! Corpus.

        Args:
            db_path: Path to a SQLite file, or ':memory:' for an in-memory corpus.
            seed:    Load the v0.1 demonstration entities (Socrates, Aspirin,
                     Sherlock Holmes and the rest). Leave on for demos and tests;
                     turn off for a corpus of your own, or the demo rows mix in
                     with your evidence.
        """
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self.migrations_applied = migrate(self._conn)
        self._conn.execute("PRAGMA foreign_keys = ON")
        if seed:
            self._load_seed_data()

    # -------------------------------------------------------------------------
    # Internal writers (named columns, so schema growth cannot shift values)
    # -------------------------------------------------------------------------

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _insert_entity(self, cur, entity_id, canonical_name, entity_type, status,
                       confidence, notes=None, description=None, wikidata_qid=None):
        now = self._now()
        cur.execute(
            """INSERT INTO entities
               (entity_id, canonical_name, entity_type, status, confidence,
                created_at, updated_at, notes, description, wikidata_qid)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (entity_id, canonical_name, entity_type, status, confidence,
             now, now, notes, description, wikidata_qid),
        )

    def _insert_alias(self, cur, entity_id, alias_name, alias_type):
        cur.execute(
            """INSERT OR IGNORE INTO aliases (alias_id, entity_id, alias_name, alias_type)
               VALUES (?, ?, ?, ?)""",
            (str(uuid.uuid4()), entity_id, alias_name, alias_type),
        )

    def _insert_provenance(self, cur, entity_id, source_type, source_url, reliability,
                           kind=ProvenanceKind.RESOLVABLE.value, source_title=None,
                           source_date=None, back_reference=None,
                           verification_method="AUTOMATED", evidence_snippet=None,
                           notes=None) -> str:
        prov_id = str(uuid.uuid4())
        cur.execute(
            """INSERT INTO provenance
               (provenance_id, entity_id, source_type, source_url, source_title,
                source_date, reliability_score, retrieved_date, verification_method,
                provenance_kind, evidence_snippet, back_reference, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (prov_id, entity_id, source_type, source_url, source_title, source_date,
             reliability, self._now(), verification_method, kind, evidence_snippet,
             back_reference, notes),
        )
        return prov_id

    def _insert_property(self, cur, entity_id, name, value, confidence, prov_id) -> str:
        prop_id = str(uuid.uuid4())
        cur.execute(
            """INSERT INTO properties
               (property_id, entity_id, property_name, property_value, confidence, provenance_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (prop_id, entity_id, name, value, confidence, prov_id),
        )
        return prop_id

    def _load_seed_data(self) -> None:
        """Populate corpus with v0.1 seed entities, skipping existing records."""
        cur = self._conn.cursor()
        for entity in SEED_DATA:
            cur.execute("SELECT 1 FROM entities WHERE entity_id = ?", (entity["entity_id"],))
            if cur.fetchone():
                continue
            self._insert_entity(
                cur, entity["entity_id"], entity["canonical_name"],
                entity["entity_type"].value, entity["status"].value,
                entity["confidence"], notes=entity.get("notes"),
            )
            self._insert_alias(cur, entity["entity_id"], entity["canonical_name"], "CANONICAL")
            for alias_name, alias_type in entity.get("aliases", []):
                self._insert_alias(cur, entity["entity_id"], alias_name, alias_type)
            source_type, source_url, reliability = entity["provenance"]
            prov_id = self._insert_provenance(
                cur, entity["entity_id"], source_type, source_url, reliability
            )
            for prop_name, prop_value in entity.get("properties", []):
                self._insert_property(
                    cur, entity["entity_id"], prop_name, prop_value, entity["confidence"], prov_id
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
            fuzzy: Enable fuzzy (partial) matching (not yet implemented).
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
            result = ExistenceResult(
                entity_name=entity_name,
                existence_status=ExistenceStatus(entity_row["status"]),
                confidence=entity_row["confidence"],
                entity_id=entity_row["entity_id"],
                canonical_name=entity_row["canonical_name"],
                entity_type=EntityType(entity_row["entity_type"]),
                provenance=self._provenance_from_row(prov_row) if prov_row else None,
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

    def resolve_identity(self, entity_a: str, entity_b: str) -> IdentityResult:
        """
        Determine the identity relation between two names (Wessel 1992, D1 to D4).

        Order of evidence:
          1. Both names resolve to the same corpus entity: x = y.
          2. A stored identity relation between the two entities.
          3. Two distinct corpus entities that both EXIST: x ≠ y, at reduced
             confidence, because it is inferred from distinct records rather
             than from a recorded distinguishing property.
          4. Otherwise UNKNOWN.

        Lookups here are not written to the audit log; only check_existence is.
        """
        row_a = self._find_entity(entity_a.strip(), True)
        row_b = self._find_entity(entity_b.strip(), True)
        id_a = row_a["entity_id"] if row_a else None
        id_b = row_b["entity_id"] if row_b else None
        both_exist = bool(
            row_a and row_b
            and row_a["status"] == ExistenceStatus.EXISTS.value
            and row_b["status"] == ExistenceStatus.EXISTS.value
        )

        def result(rel: IdentityRelationType, conf: float, symbol: Optional[str] = None):
            return IdentityResult(
                entity_a=entity_a, entity_b=entity_b, relation_type=rel,
                ntp_relation=symbol or NTP_SYMBOLS[rel], confidence=conf,
                both_exist=both_exist, entity_a_id=id_a, entity_b_id=id_b,
            )

        if id_a and id_b:
            conf = min(row_a["confidence"], row_b["confidence"])
            if id_a == id_b:
                return result(IdentityRelationType.SAME_AS, conf)
            stored = self._conn.execute(
                """SELECT relation_type, ntp_symbol, confidence FROM identity_relations
                   WHERE (entity_a_id = ? AND entity_b_id = ?)
                      OR (entity_a_id = ? AND entity_b_id = ?)
                   ORDER BY confidence DESC LIMIT 1""",
                (id_a, id_b, id_b, id_a),
            ).fetchone()
            if stored:
                return result(IdentityRelationType(stored["relation_type"]),
                              stored["confidence"], stored["ntp_symbol"])
            if both_exist:
                return result(IdentityRelationType.DIFFERENT, conf * 0.9)
        return result(IdentityRelationType.UNKNOWN, 0.0)

    def search_entities(
        self,
        query: str,
        limit: int = 10,
        entity_type: Optional[EntityType] = None,
        existence_status: Optional[ExistenceStatus] = None,
    ) -> List[ExistenceResult]:
        """Substring search over canonical names and aliases. Not audited."""
        like = f"%{query.strip().lower()}%"
        sql = """SELECT DISTINCT e.* FROM entities e
                 LEFT JOIN aliases a ON e.entity_id = a.entity_id
                 WHERE (LOWER(e.canonical_name) LIKE ? OR LOWER(a.alias_name) LIKE ?)"""
        params: List[Any] = [like, like]
        if entity_type:
            sql += " AND e.entity_type = ?"
            params.append(entity_type.value)
        if existence_status:
            sql += " AND e.status = ?"
            params.append(existence_status.value)
        sql += " ORDER BY e.confidence DESC, e.canonical_name LIMIT ?"
        params.append(limit)
        out = []
        for row in self._conn.execute(sql, params).fetchall():
            prov = self._get_provenance(row["entity_id"])
            out.append(ExistenceResult(
                entity_name=row["canonical_name"],
                existence_status=ExistenceStatus(row["status"]),
                confidence=row["confidence"],
                entity_id=row["entity_id"],
                canonical_name=row["canonical_name"],
                entity_type=EntityType(row["entity_type"]),
                provenance=self._provenance_from_row(prov) if prov else None,
            ))
        return out

    def get_corpus_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the E! Corpus."""
        q = lambda sql: self._conn.execute(sql).fetchone()[0]  # noqa: E731
        return {
            "schema_version": SCHEMA_VERSION,
            "existing_entities": q("SELECT COUNT(*) FROM entities WHERE status = 'EXISTS'"),
            "confirmed_nonexistent": q("SELECT COUNT(*) FROM entities WHERE status = 'NOT_EXISTS'"),
            "alias_records": q("SELECT COUNT(*) FROM aliases"),
            "property_records": q("SELECT COUNT(*) FROM properties"),
            "provenance_records": q("SELECT COUNT(*) FROM provenance"),
            "provenance_resolvable": q("SELECT COUNT(*) FROM provenance WHERE provenance_kind = 'resolvable'"),
            "provenance_named": q("SELECT COUNT(*) FROM provenance WHERE provenance_kind = 'named'"),
            "identity_relations": q("SELECT COUNT(*) FROM identity_relations"),
            "queries_logged": q("SELECT COUNT(*) FROM audit_log"),
        }

    def add_entity(
        self,
        canonical_name: str,
        entity_type: EntityType,
        status: ExistenceStatus,
        source_type: str,
        source_url: Optional[str] = None,
        reliability_score: float = 0.85,
        aliases: Optional[List[tuple]] = None,
        properties: Optional[List[tuple]] = None,
        confidence: float = 0.9,
        notes: Optional[str] = None,
        *,
        provenance_kind: ProvenanceKind = ProvenanceKind.RESOLVABLE,
        source_title: Optional[str] = None,
        source_date: Optional[str] = None,
        back_reference: Optional[str] = None,
        description: Optional[str] = None,
        wikidata_qid: Optional[str] = None,
        verification_method: str = "MANUAL",
    ) -> str:
        """
        Add a new entity to the E! Corpus, with the evidence for it.

        A RESOLVABLE source needs ``source_url``. A NAMED source needs
        ``source_title`` (what the source is called) and may omit the URL.
        ``back_reference`` records where the source was found and is never
        treated as evidence.

        Returns the new entity_id.
        """
        kind = ProvenanceKind(provenance_kind)
        if not canonical_name or not canonical_name.strip():
            raise ValueError("canonical_name is required")
        if kind is ProvenanceKind.RESOLVABLE and not (source_url or "").strip():
            raise ValueError("a resolvable source needs source_url; "
                             "use provenance_kind=NAMED with source_title otherwise")
        if kind is ProvenanceKind.NAMED and not (source_title or "").strip():
            raise ValueError("a named source needs source_title")
        if self._find_entity(canonical_name.strip(), True):
            raise ValueError(f"'{canonical_name}' is already in the corpus (by name or alias)")

        entity_id = f"ent-{uuid.uuid4().hex[:12]}"
        cur = self._conn.cursor()
        try:
            self._insert_entity(cur, entity_id, canonical_name.strip(), entity_type.value,
                                status.value, confidence, notes=notes,
                                description=description, wikidata_qid=wikidata_qid)
            self._insert_alias(cur, entity_id, canonical_name.strip(), "CANONICAL")
            for alias_name, alias_type in (aliases or []):
                self._insert_alias(cur, entity_id, alias_name, alias_type)
            prov_id = self._insert_provenance(
                cur, entity_id, source_type, (source_url or None), reliability_score,
                kind=kind.value, source_title=source_title, source_date=source_date,
                back_reference=back_reference, verification_method=verification_method,
            )
            for prop_name, prop_value in (properties or []):
                self._insert_property(cur, entity_id, prop_name, prop_value, confidence, prov_id)
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        return entity_id

    def add_property(self, entity_id: str, property_name: str, property_value: str,
                     confidence: float = 0.5, provenance_id: Optional[str] = None) -> str:
        """Attach a property (a predicate) to an existing entity."""
        cur = self._conn.cursor()
        prop_id = self._insert_property(cur, entity_id, property_name, property_value,
                                        confidence, provenance_id)
        self._conn.commit()
        return prop_id

    def add_identity_relation(self, entity_a_id: str, entity_b_id: str,
                              relation_type: IdentityRelationType,
                              confidence: float = 0.5,
                              provenance_id: Optional[str] = None) -> str:
        """Record an identity relation (D1 to D4) between two corpus entities."""
        relation_id = f"rel-{uuid.uuid4().hex[:12]}"
        self._conn.execute(
            """INSERT INTO identity_relations
               (relation_id, entity_a_id, entity_b_id, relation_type, ntp_symbol,
                confidence, provenance_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (relation_id, entity_a_id, entity_b_id, relation_type.value,
             NTP_SYMBOLS[relation_type], confidence, provenance_id, self._now()),
        )
        self._conn.commit()
        return relation_id

    # -------------------------------------------------------------------------
    # Private Helpers
    # -------------------------------------------------------------------------

    def _find_entity(self, name: str, include_aliases: bool) -> Optional[sqlite3.Row]:
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM entities WHERE canonical_name = ? COLLATE NOCASE", (name,))
        row = cur.fetchone()
        if row:
            return row
        if include_aliases:
            cur.execute(
                """SELECT e.* FROM entities e
                   JOIN aliases a ON e.entity_id = a.entity_id
                   WHERE a.alias_name = ? COLLATE NOCASE""",
                (name,),
            )
            return cur.fetchone()
        return None

    def _get_provenance(self, entity_id: str) -> Optional[sqlite3.Row]:
        # A resolvable source outranks a named one at equal reliability.
        return self._conn.execute(
            """SELECT * FROM provenance WHERE entity_id = ?
               ORDER BY reliability_score DESC,
                        CASE provenance_kind WHEN 'resolvable' THEN 0 ELSE 1 END
               LIMIT 1""",
            (entity_id,),
        ).fetchone()

    @staticmethod
    def _provenance_from_row(row: sqlite3.Row) -> Provenance:
        return Provenance(
            source_type=row["source_type"],
            source_url=row["source_url"],
            reliability_score=row["reliability_score"],
            retrieved_date=row["retrieved_date"],
            notes=row["notes"],
            provenance_kind=row["provenance_kind"],
            source_title=row["source_title"],
            source_date=row["source_date"],
            back_reference=row["back_reference"],
        )

    def _get_properties(self, entity_id: str) -> List[Dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT property_name, property_value, confidence FROM properties WHERE entity_id = ?",
            (entity_id,),
        )
        return [dict(row) for row in cur.fetchall()]

    def _audit(self, normalised_name: str, result: ExistenceResult,
               pipeline_run_id: Optional[str]) -> None:
        self._conn.execute(
            """INSERT INTO audit_log
               (log_id, query_name, normalised_name, result_status, confidence,
                timestamp, pipeline_run_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), result.entity_name, normalised_name,
             result.existence_status.value, result.confidence, self._now(), pipeline_run_id),
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
