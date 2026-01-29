"""
V.E.R.A. E! Corpus Schema & Verification Service
=================================================
Layer 2 of the Triple-Layer Verification System

The E! Corpus is the Evidence-Based Existence Knowledge Base that serves as
the foundational truth layer for V.E.R.A. It stores verified existence claims
with full provenance tracking, enabling the system to distinguish between
entities that exist (E!) and those that do not (~E!).

Architecture Role:
- Layer 2: E! Verification Service in Triple-Layer Verification
- Implements IF-002: E! Corpus API from VERA_Interface_Specifications_v1.0
- Implements SVC-002: Existence Lookup Service from VERA_Business_Service_Catalog_v1.0

Source: VERA_E_Corpus_Data_Model_v1.0.docx

Author: V.E.R.A. Open Source Initiative
Version: 0.1.0 (Prototype)
Date: January 2026
"""

import sqlite3
import uuid
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
import re


# =============================================================================
# Enumerations (from VERA_E_Corpus_Data_Model_v1.0)
# =============================================================================

class ExistenceStatus(Enum):
    """
    Existence status in NTP terms.
    
    E!   = EXISTS      - Entity verified to exist with evidence
    ~E!  = NOT_EXISTS  - Entity confirmed not to exist (fictional, etc.)
    ?E!  = UNKNOWN     - Existence status cannot be determined
    """
    EXISTS = "EXISTS"
    NOT_EXISTS = "NOT_EXISTS"
    UNKNOWN = "UNKNOWN"


class EntityType(Enum):
    """Entity type classification."""
    PERSON = "PERSON"
    PLACE = "PLACE"
    THING = "THING"
    EVENT = "EVENT"
    CONCEPT = "CONCEPT"
    ORGANIZATION = "ORGANIZATION"
    FICTIONAL = "FICTIONAL"
    MYTHOLOGICAL = "MYTHOLOGICAL"


class SourceType(Enum):
    """Provenance source type classification."""
    WIKIPEDIA = "WIKIPEDIA"
    WIKIDATA = "WIKIDATA"
    SCIENTIFIC = "SCIENTIFIC"
    GOVERNMENT = "GOVERNMENT"
    NEWS = "NEWS"
    MANUAL = "MANUAL"
    OTHER = "OTHER"


class VerificationMethod(Enum):
    """How the existence was verified."""
    AUTOMATED = "AUTOMATED"
    MANUAL = "MANUAL"
    HYBRID = "HYBRID"


class IdentityRelationType(Enum):
    """
    NTP Identity relation types (D1-D4).
    
    From Wessel (1992) Section 5.
    """
    SAME_AS = "SAME_AS"                      # x = y: Verified identical entity
    DIFFERENT = "DIFFERENT"                   # x ≠ y: D3 - Verified different (both exist)
    WEAK_INDISCERNIBLE = "WEAK_INDISCERNIBLE" # ~(x#y): D2 - No distinguishing property
    STRONG_INDISCERNIBLE = "STRONG_INDISCERNIBLE"  # ~(x ≠ y): D4 - Context-sensitive same
    UNKNOWN = "UNKNOWN"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class Provenance:
    """Provenance record for tracking evidence sources."""
    provenance_id: str
    entity_id: str
    source_type: SourceType
    source_url: str
    source_title: Optional[str] = None
    source_date: Optional[str] = None
    retrieval_date: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    verification_method: VerificationMethod = VerificationMethod.AUTOMATED
    reliability_score: float = 0.5
    evidence_snippet: Optional[str] = None
    verified_by: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class Entity:
    """Primary entity record in the E! Corpus."""
    entity_id: str
    canonical_name: str
    entity_type: EntityType
    existence_status: ExistenceStatus
    existence_confidence: float
    primary_source_id: str
    wikidata_qid: Optional[str] = None
    wikipedia_url: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    verified_at: Optional[str] = None
    is_active: bool = True
    description: Optional[str] = None


@dataclass
class Alias:
    """Alternative name for an entity."""
    alias_id: str
    entity_id: str
    alias_name: str
    alias_type: str = "ALTERNATE"  # ALTERNATE, ABBREVIATION, FORMER, etc.
    language: str = "en"
    is_primary: bool = False


@dataclass
class Property:
    """Property (predicate) attached to an entity."""
    property_id: str
    entity_id: str
    property_name: str
    property_value: str
    value_type: str = "STRING"  # STRING, NUMBER, DATE, BOOLEAN, REFERENCE
    unit: Optional[str] = None
    provenance_id: str = ""
    confidence: float = 0.5
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    is_current: bool = True


@dataclass
class IdentityRelation:
    """Identity relation between two entities (D1-D4)."""
    relation_id: str
    entity_a_id: str
    entity_b_id: str
    relation_type: IdentityRelationType
    ntp_symbol: str  # x = y, x ≠ y, ~(x#y), ~(x ≠ y)
    confidence: float
    provenance_id: str


@dataclass
class ExistenceResult:
    """Result of an existence check."""
    entity_id: Optional[str]
    canonical_name: str
    existence_status: ExistenceStatus
    confidence: float
    entity_type: Optional[EntityType]
    provenance: Optional[Dict[str, Any]]
    found_in_corpus: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "canonical_name": self.canonical_name,
            "existence_status": self.existence_status.value,
            "confidence": self.confidence,
            "entity_type": self.entity_type.value if self.entity_type else None,
            "provenance": self.provenance,
            "found_in_corpus": self.found_in_corpus
        }


@dataclass
class IdentityResult:
    """Result of an identity resolution."""
    entity_a: str
    entity_b: str
    relation_type: IdentityRelationType
    ntp_relation: str
    confidence: float
    both_exist: bool
    entity_a_id: Optional[str]
    entity_b_id: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_a": self.entity_a,
            "entity_b": self.entity_b,
            "relation_type": self.relation_type.value,
            "ntp_relation": self.ntp_relation,
            "confidence": self.confidence,
            "both_exist": self.both_exist,
            "entity_a_id": self.entity_a_id,
            "entity_b_id": self.entity_b_id
        }


# =============================================================================
# E! Corpus Database Schema
# =============================================================================

class ECorpusSchema:
    """
    SQLite schema for the E! Corpus.
    
    Designed for PostgreSQL compatibility - can be migrated with minimal changes.
    """
    
    SCHEMA_SQL = """
    -- E! Corpus Schema v1.0
    -- V.E.R.A. - Verified Existence and Reason Architecture
    
    -- Entity table: Core existence claims
    CREATE TABLE IF NOT EXISTS entities (
        entity_id TEXT PRIMARY KEY,
        canonical_name TEXT NOT NULL,
        entity_type TEXT NOT NULL CHECK (entity_type IN 
            ('PERSON', 'PLACE', 'THING', 'EVENT', 'CONCEPT', 
             'ORGANIZATION', 'FICTIONAL', 'MYTHOLOGICAL')),
        existence_status TEXT NOT NULL CHECK (existence_status IN 
            ('EXISTS', 'NOT_EXISTS', 'UNKNOWN')),
        existence_confidence REAL NOT NULL CHECK (existence_confidence >= 0 AND existence_confidence <= 1),
        primary_source_id TEXT,
        wikidata_qid TEXT,
        wikipedia_url TEXT,
        description TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        verified_at TEXT,
        is_active INTEGER NOT NULL DEFAULT 1
    );
    
    -- Aliases table: Alternative names for entities
    CREATE TABLE IF NOT EXISTS aliases (
        alias_id TEXT PRIMARY KEY,
        entity_id TEXT NOT NULL,
        alias_name TEXT NOT NULL,
        alias_type TEXT DEFAULT 'ALTERNATE',
        language TEXT DEFAULT 'en',
        is_primary INTEGER DEFAULT 0,
        FOREIGN KEY (entity_id) REFERENCES entities(entity_id)
    );
    
    -- Provenance table: Evidence sources
    CREATE TABLE IF NOT EXISTS provenance (
        provenance_id TEXT PRIMARY KEY,
        entity_id TEXT NOT NULL,
        source_type TEXT NOT NULL CHECK (source_type IN 
            ('WIKIPEDIA', 'WIKIDATA', 'SCIENTIFIC', 'GOVERNMENT', 'NEWS', 'MANUAL', 'OTHER')),
        source_url TEXT NOT NULL,
        source_title TEXT,
        source_date TEXT,
        retrieval_date TEXT NOT NULL,
        verification_method TEXT DEFAULT 'AUTOMATED' CHECK (verification_method IN 
            ('AUTOMATED', 'MANUAL', 'HYBRID')),
        reliability_score REAL DEFAULT 0.5 CHECK (reliability_score >= 0 AND reliability_score <= 1),
        evidence_snippet TEXT,
        verified_by TEXT,
        notes TEXT,
        FOREIGN KEY (entity_id) REFERENCES entities(entity_id)
    );
    
    -- Properties table: Predicates about entities
    CREATE TABLE IF NOT EXISTS properties (
        property_id TEXT PRIMARY KEY,
        entity_id TEXT NOT NULL,
        property_name TEXT NOT NULL,
        property_value TEXT NOT NULL,
        value_type TEXT DEFAULT 'STRING' CHECK (value_type IN 
            ('STRING', 'NUMBER', 'DATE', 'BOOLEAN', 'REFERENCE')),
        unit TEXT,
        provenance_id TEXT,
        confidence REAL DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),
        valid_from TEXT,
        valid_to TEXT,
        is_current INTEGER DEFAULT 1,
        FOREIGN KEY (entity_id) REFERENCES entities(entity_id),
        FOREIGN KEY (provenance_id) REFERENCES provenance(provenance_id)
    );
    
    -- Identity relations table: D1-D4 relations between entities
    CREATE TABLE IF NOT EXISTS identity_relations (
        relation_id TEXT PRIMARY KEY,
        entity_a_id TEXT NOT NULL,
        entity_b_id TEXT NOT NULL,
        relation_type TEXT NOT NULL CHECK (relation_type IN 
            ('SAME_AS', 'DIFFERENT', 'WEAK_INDISCERNIBLE', 'STRONG_INDISCERNIBLE', 'UNKNOWN')),
        ntp_symbol TEXT NOT NULL,
        confidence REAL DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),
        provenance_id TEXT,
        FOREIGN KEY (entity_a_id) REFERENCES entities(entity_id),
        FOREIGN KEY (entity_b_id) REFERENCES entities(entity_id),
        FOREIGN KEY (provenance_id) REFERENCES provenance(provenance_id)
    );
    
    -- Indexes for performance
    CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(canonical_name);
    CREATE INDEX IF NOT EXISTS idx_entities_status ON entities(existence_status);
    CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
    CREATE INDEX IF NOT EXISTS idx_entities_wikidata ON entities(wikidata_qid);
    CREATE INDEX IF NOT EXISTS idx_aliases_name ON aliases(alias_name);
    CREATE INDEX IF NOT EXISTS idx_aliases_entity ON aliases(entity_id);
    CREATE INDEX IF NOT EXISTS idx_properties_entity ON properties(entity_id);
    CREATE INDEX IF NOT EXISTS idx_properties_name ON properties(property_name);
    CREATE INDEX IF NOT EXISTS idx_provenance_entity ON provenance(entity_id);
    
    -- Full-text search (SQLite FTS5)
    CREATE VIRTUAL TABLE IF NOT EXISTS entities_fts USING fts5(
        canonical_name,
        description,
        content='entities',
        content_rowid='rowid'
    );
    
    CREATE VIRTUAL TABLE IF NOT EXISTS aliases_fts USING fts5(
        alias_name,
        content='aliases',
        content_rowid='rowid'
    );
    """
    
    @classmethod
    def create_schema(cls, conn: sqlite3.Connection):
        """Create all tables and indexes."""
        conn.executescript(cls.SCHEMA_SQL)
        conn.commit()


# =============================================================================
# E! Verification Service (Layer 2)
# =============================================================================

class EVerificationService:
    """
    E! Verification Service - Layer 2 of V.E.R.A.
    
    Implements IF-002: E! Corpus API from VERA_Interface_Specifications_v1.0
    
    Core operations:
    - exists(): Check if an entity exists in the E! Corpus
    - get_entity(): Retrieve full entity record
    - get_properties(): Get properties for an entity
    - resolve_identity(): Determine if two names refer to the same entity
    - search_entities(): Search entities by name/alias
    """
    
    def __init__(self, db_path: str = ":memory:"):
        """
        Initialize the E! Verification Service.
        
        Args:
            db_path: Path to SQLite database, or ":memory:" for in-memory
        """
        self.db_path = db_path
        self.conn = sqlite3.Connection(db_path)
        self.conn.row_factory = sqlite3.Row
        ECorpusSchema.create_schema(self.conn)
    
    def _generate_id(self, prefix: str = "e") -> str:
        """Generate a unique ID."""
        return f"{prefix}-{uuid.uuid4().hex[:12]}"
    
    def _normalize_name(self, name: str) -> str:
        """Normalize entity name for matching."""
        # Lowercase, strip whitespace, normalize spaces
        normalized = name.lower().strip()
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized
    
    # =========================================================================
    # Core API Operations (IF-002)
    # =========================================================================
    
    def exists(
        self, 
        entity_name: str, 
        fuzzy: bool = False,
        include_aliases: bool = True
    ) -> ExistenceResult:
        """
        Check if an entity exists in the E! Corpus.
        
        Endpoint: GET /api/v1/exists/{entity_name}
        
        Args:
            entity_name: Name or identifier of entity to check
            fuzzy: Enable fuzzy matching (default: False)
            include_aliases: Search aliases (default: True)
            
        Returns:
            ExistenceResult with status, confidence, and provenance
        """
        normalized = self._normalize_name(entity_name)
        
        # First, try exact match on canonical name
        cursor = self.conn.execute("""
            SELECT e.*, p.source_type, p.source_url, p.reliability_score
            FROM entities e
            LEFT JOIN provenance p ON e.primary_source_id = p.provenance_id
            WHERE LOWER(e.canonical_name) = ? AND e.is_active = 1
        """, (normalized,))
        
        row = cursor.fetchone()
        
        # If not found, try aliases
        if row is None and include_aliases:
            cursor = self.conn.execute("""
                SELECT e.*, p.source_type, p.source_url, p.reliability_score
                FROM entities e
                JOIN aliases a ON e.entity_id = a.entity_id
                LEFT JOIN provenance p ON e.primary_source_id = p.provenance_id
                WHERE LOWER(a.alias_name) = ? AND e.is_active = 1
            """, (normalized,))
            row = cursor.fetchone()
        
        # If still not found and fuzzy enabled, try LIKE search
        if row is None and fuzzy:
            cursor = self.conn.execute("""
                SELECT e.*, p.source_type, p.source_url, p.reliability_score
                FROM entities e
                LEFT JOIN provenance p ON e.primary_source_id = p.provenance_id
                WHERE LOWER(e.canonical_name) LIKE ? AND e.is_active = 1
                ORDER BY e.existence_confidence DESC
                LIMIT 1
            """, (f"%{normalized}%",))
            row = cursor.fetchone()
        
        if row:
            provenance = None
            if row['source_type']:
                provenance = {
                    "source_type": row['source_type'],
                    "source_url": row['source_url'],
                    "reliability_score": row['reliability_score']
                }
            
            return ExistenceResult(
                entity_id=row['entity_id'],
                canonical_name=row['canonical_name'],
                existence_status=ExistenceStatus(row['existence_status']),
                confidence=row['existence_confidence'],
                entity_type=EntityType(row['entity_type']),
                provenance=provenance,
                found_in_corpus=True
            )
        
        # Not found in corpus - return UNKNOWN
        return ExistenceResult(
            entity_id=None,
            canonical_name=entity_name,
            existence_status=ExistenceStatus.UNKNOWN,
            confidence=0.0,
            entity_type=None,
            provenance=None,
            found_in_corpus=False
        )
    
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """
        Retrieve full entity record by ID.
        
        Args:
            entity_id: Entity identifier
            
        Returns:
            Entity object or None if not found
        """
        cursor = self.conn.execute("""
            SELECT * FROM entities WHERE entity_id = ? AND is_active = 1
        """, (entity_id,))
        
        row = cursor.fetchone()
        if row:
            return Entity(
                entity_id=row['entity_id'],
                canonical_name=row['canonical_name'],
                entity_type=EntityType(row['entity_type']),
                existence_status=ExistenceStatus(row['existence_status']),
                existence_confidence=row['existence_confidence'],
                primary_source_id=row['primary_source_id'] or "",
                wikidata_qid=row['wikidata_qid'],
                wikipedia_url=row['wikipedia_url'],
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                verified_at=row['verified_at'],
                is_active=bool(row['is_active']),
                description=row['description']
            )
        return None
    
    def get_properties(self, entity_id: str) -> List[Property]:
        """
        Retrieve all properties for an entity.
        
        Per NTP R1: Properties are only meaningful when attached to
        entities with verified existence.
        
        Args:
            entity_id: Entity identifier
            
        Returns:
            List of Property objects
        """
        # First check existence status
        entity = self.get_entity(entity_id)
        if not entity:
            return []
        
        cursor = self.conn.execute("""
            SELECT * FROM properties 
            WHERE entity_id = ? AND is_current = 1
            ORDER BY property_name
        """, (entity_id,))
        
        properties = []
        for row in cursor.fetchall():
            properties.append(Property(
                property_id=row['property_id'],
                entity_id=row['entity_id'],
                property_name=row['property_name'],
                property_value=row['property_value'],
                value_type=row['value_type'],
                unit=row['unit'],
                provenance_id=row['provenance_id'] or "",
                confidence=row['confidence'],
                valid_from=row['valid_from'],
                valid_to=row['valid_to'],
                is_current=bool(row['is_current'])
            ))
        
        return properties
    
    def resolve_identity(
        self, 
        entity_a: str, 
        entity_b: str,
        context: Optional[str] = None
    ) -> IdentityResult:
        """
        Determine if two names refer to the same entity.
        
        Implements NTP identity relations D1-D4 from Wessel (1992).
        
        D3: x ≠ y requires E!(x) ∧ E!(y) - both must exist
        D4: ~(x ≠ y) strong indiscernibility for identity
        
        Args:
            entity_a: First entity name
            entity_b: Second entity name
            context: Optional context for disambiguation
            
        Returns:
            IdentityResult with relation type and NTP symbol
        """
        # Look up both entities
        result_a = self.exists(entity_a)
        result_b = self.exists(entity_b)
        
        # Check if both exist
        a_exists = result_a.existence_status == ExistenceStatus.EXISTS
        b_exists = result_b.existence_status == ExistenceStatus.EXISTS
        both_exist = a_exists and b_exists
        
        # If same entity ID, they're identical
        if result_a.entity_id and result_b.entity_id:
            if result_a.entity_id == result_b.entity_id:
                return IdentityResult(
                    entity_a=entity_a,
                    entity_b=entity_b,
                    relation_type=IdentityRelationType.SAME_AS,
                    ntp_relation="x = y",
                    confidence=min(result_a.confidence, result_b.confidence),
                    both_exist=both_exist,
                    entity_a_id=result_a.entity_id,
                    entity_b_id=result_b.entity_id
                )
        
        # Check stored identity relations
        if result_a.entity_id and result_b.entity_id:
            cursor = self.conn.execute("""
                SELECT * FROM identity_relations
                WHERE (entity_a_id = ? AND entity_b_id = ?)
                   OR (entity_a_id = ? AND entity_b_id = ?)
            """, (result_a.entity_id, result_b.entity_id, 
                  result_b.entity_id, result_a.entity_id))
            
            rel = cursor.fetchone()
            if rel:
                return IdentityResult(
                    entity_a=entity_a,
                    entity_b=entity_b,
                    relation_type=IdentityRelationType(rel['relation_type']),
                    ntp_relation=rel['ntp_symbol'],
                    confidence=rel['confidence'],
                    both_exist=both_exist,
                    entity_a_id=result_a.entity_id,
                    entity_b_id=result_b.entity_id
                )
        
        # Both found but different IDs - they're different (D3)
        if result_a.entity_id and result_b.entity_id:
            if both_exist:
                return IdentityResult(
                    entity_a=entity_a,
                    entity_b=entity_b,
                    relation_type=IdentityRelationType.DIFFERENT,
                    ntp_relation="x ≠ y",
                    confidence=min(result_a.confidence, result_b.confidence) * 0.9,
                    both_exist=True,
                    entity_a_id=result_a.entity_id,
                    entity_b_id=result_b.entity_id
                )
        
        # Cannot determine - return UNKNOWN
        return IdentityResult(
            entity_a=entity_a,
            entity_b=entity_b,
            relation_type=IdentityRelationType.UNKNOWN,
            ntp_relation="?",
            confidence=0.0,
            both_exist=both_exist,
            entity_a_id=result_a.entity_id,
            entity_b_id=result_b.entity_id
        )
    
    def search_entities(
        self, 
        query: str, 
        limit: int = 10,
        entity_type: Optional[EntityType] = None,
        existence_status: Optional[ExistenceStatus] = None
    ) -> List[Entity]:
        """
        Search entities by name or alias.
        
        Args:
            query: Search query
            limit: Maximum results to return
            entity_type: Filter by entity type
            existence_status: Filter by existence status
            
        Returns:
            List of matching Entity objects
        """
        normalized = f"%{self._normalize_name(query)}%"
        
        sql = """
            SELECT DISTINCT e.* FROM entities e
            LEFT JOIN aliases a ON e.entity_id = a.entity_id
            WHERE (LOWER(e.canonical_name) LIKE ? OR LOWER(a.alias_name) LIKE ?)
            AND e.is_active = 1
        """
        params = [normalized, normalized]
        
        if entity_type:
            sql += " AND e.entity_type = ?"
            params.append(entity_type.value)
        
        if existence_status:
            sql += " AND e.existence_status = ?"
            params.append(existence_status.value)
        
        sql += " ORDER BY e.existence_confidence DESC LIMIT ?"
        params.append(limit)
        
        cursor = self.conn.execute(sql, params)
        
        entities = []
        for row in cursor.fetchall():
            entities.append(Entity(
                entity_id=row['entity_id'],
                canonical_name=row['canonical_name'],
                entity_type=EntityType(row['entity_type']),
                existence_status=ExistenceStatus(row['existence_status']),
                existence_confidence=row['existence_confidence'],
                primary_source_id=row['primary_source_id'] or "",
                wikidata_qid=row['wikidata_qid'],
                wikipedia_url=row['wikipedia_url'],
                description=row['description']
            ))
        
        return entities
    
    # =========================================================================
    # Data Management Operations
    # =========================================================================
    
    def add_entity(
        self,
        canonical_name: str,
        entity_type: EntityType,
        existence_status: ExistenceStatus,
        confidence: float = 0.5,
        wikidata_qid: Optional[str] = None,
        wikipedia_url: Optional[str] = None,
        description: Optional[str] = None,
        source_type: SourceType = SourceType.MANUAL,
        source_url: str = "",
        aliases: Optional[List[str]] = None
    ) -> Entity:
        """
        Add a new entity to the E! Corpus.
        
        Args:
            canonical_name: Primary name for the entity
            entity_type: Type classification
            existence_status: E!, ~E!, or ?E!
            confidence: Confidence score 0.0-1.0
            wikidata_qid: Wikidata Q identifier if available
            wikipedia_url: Wikipedia article URL if available
            description: Entity description
            source_type: Type of evidence source
            source_url: URL to evidence source
            aliases: Alternative names
            
        Returns:
            Created Entity object
        """
        entity_id = self._generate_id("ent")
        provenance_id = self._generate_id("prov")
        now = datetime.utcnow().isoformat()
        
        # Create provenance record
        self.conn.execute("""
            INSERT INTO provenance 
            (provenance_id, entity_id, source_type, source_url, retrieval_date, reliability_score)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (provenance_id, entity_id, source_type.value, source_url, now, confidence))
        
        # Create entity
        self.conn.execute("""
            INSERT INTO entities
            (entity_id, canonical_name, entity_type, existence_status, 
             existence_confidence, primary_source_id, wikidata_qid, wikipedia_url,
             description, created_at, updated_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (entity_id, canonical_name, entity_type.value, existence_status.value,
              confidence, provenance_id, wikidata_qid, wikipedia_url, description, now, now))
        
        # Add aliases
        if aliases:
            for alias in aliases:
                alias_id = self._generate_id("alias")
                self.conn.execute("""
                    INSERT INTO aliases (alias_id, entity_id, alias_name)
                    VALUES (?, ?, ?)
                """, (alias_id, entity_id, alias))
        
        self.conn.commit()
        
        return Entity(
            entity_id=entity_id,
            canonical_name=canonical_name,
            entity_type=entity_type,
            existence_status=existence_status,
            existence_confidence=confidence,
            primary_source_id=provenance_id,
            wikidata_qid=wikidata_qid,
            wikipedia_url=wikipedia_url,
            description=description,
            created_at=now,
            updated_at=now
        )
    
    def add_property(
        self,
        entity_id: str,
        property_name: str,
        property_value: str,
        value_type: str = "STRING",
        unit: Optional[str] = None,
        confidence: float = 0.5
    ) -> Property:
        """
        Add a property to an entity.
        
        Args:
            entity_id: Entity to attach property to
            property_name: Property name (e.g., "mass", "birthdate")
            property_value: Property value as string
            value_type: Type hint for the value
            unit: Unit of measurement if applicable
            confidence: Confidence score
            
        Returns:
            Created Property object
        """
        property_id = self._generate_id("prop")
        
        self.conn.execute("""
            INSERT INTO properties
            (property_id, entity_id, property_name, property_value, 
             value_type, unit, confidence, is_current)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """, (property_id, entity_id, property_name, property_value,
              value_type, unit, confidence))
        
        self.conn.commit()
        
        return Property(
            property_id=property_id,
            entity_id=entity_id,
            property_name=property_name,
            property_value=property_value,
            value_type=value_type,
            unit=unit,
            confidence=confidence
        )
    
    def add_identity_relation(
        self,
        entity_a_id: str,
        entity_b_id: str,
        relation_type: IdentityRelationType,
        confidence: float = 0.5
    ) -> IdentityRelation:
        """
        Add an identity relation between two entities.
        
        Args:
            entity_a_id: First entity ID
            entity_b_id: Second entity ID
            relation_type: Type of relation (D1-D4)
            confidence: Confidence score
            
        Returns:
            Created IdentityRelation object
        """
        relation_id = self._generate_id("rel")
        
        # Map relation type to NTP symbol
        ntp_symbols = {
            IdentityRelationType.SAME_AS: "x = y",
            IdentityRelationType.DIFFERENT: "x ≠ y",
            IdentityRelationType.WEAK_INDISCERNIBLE: "~(x#y)",
            IdentityRelationType.STRONG_INDISCERNIBLE: "~(x ≠ y)",
            IdentityRelationType.UNKNOWN: "?"
        }
        
        ntp_symbol = ntp_symbols[relation_type]
        
        self.conn.execute("""
            INSERT INTO identity_relations
            (relation_id, entity_a_id, entity_b_id, relation_type, ntp_symbol, confidence)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (relation_id, entity_a_id, entity_b_id, relation_type.value, ntp_symbol, confidence))
        
        self.conn.commit()
        
        return IdentityRelation(
            relation_id=relation_id,
            entity_a_id=entity_a_id,
            entity_b_id=entity_b_id,
            relation_type=relation_type,
            ntp_symbol=ntp_symbol,
            confidence=confidence,
            provenance_id=""
        )
    
    def get_corpus_stats(self) -> Dict[str, Any]:
        """Get statistics about the E! Corpus."""
        stats = {}
        
        # Total entities by status
        cursor = self.conn.execute("""
            SELECT existence_status, COUNT(*) as count
            FROM entities WHERE is_active = 1
            GROUP BY existence_status
        """)
        stats['by_status'] = {row['existence_status']: row['count'] for row in cursor}
        
        # Total entities by type
        cursor = self.conn.execute("""
            SELECT entity_type, COUNT(*) as count
            FROM entities WHERE is_active = 1
            GROUP BY entity_type
        """)
        stats['by_type'] = {row['entity_type']: row['count'] for row in cursor}
        
        # Total counts
        cursor = self.conn.execute("SELECT COUNT(*) FROM entities WHERE is_active = 1")
        stats['total_entities'] = cursor.fetchone()[0]
        
        cursor = self.conn.execute("SELECT COUNT(*) FROM aliases")
        stats['total_aliases'] = cursor.fetchone()[0]
        
        cursor = self.conn.execute("SELECT COUNT(*) FROM properties WHERE is_current = 1")
        stats['total_properties'] = cursor.fetchone()[0]
        
        cursor = self.conn.execute("SELECT COUNT(*) FROM provenance")
        stats['total_provenance_records'] = cursor.fetchone()[0]
        
        return stats
    
    def close(self):
        """Close database connection."""
        self.conn.close()


# =============================================================================
# Seed Data for Testing
# =============================================================================

def seed_test_data(service: EVerificationService):
    """
    Seed the E! Corpus with test data for validation.
    
    Includes examples from VERA architecture documents.
    """
    # Real existing entities
    socrates = service.add_entity(
        canonical_name="Socrates",
        entity_type=EntityType.PERSON,
        existence_status=ExistenceStatus.EXISTS,
        confidence=0.99,
        wikidata_qid="Q913",
        wikipedia_url="https://en.wikipedia.org/wiki/Socrates",
        description="Ancient Greek philosopher",
        source_type=SourceType.WIKIDATA,
        source_url="https://www.wikidata.org/wiki/Q913",
        aliases=["Σωκράτης"]
    )
    
    einstein = service.add_entity(
        canonical_name="Albert Einstein",
        entity_type=EntityType.PERSON,
        existence_status=ExistenceStatus.EXISTS,
        confidence=0.99,
        wikidata_qid="Q937",
        wikipedia_url="https://en.wikipedia.org/wiki/Albert_Einstein",
        description="German-born theoretical physicist",
        source_type=SourceType.WIKIDATA,
        source_url="https://www.wikidata.org/wiki/Q937",
        aliases=["A. Einstein", "Einstein"]
    )
    
    higgs = service.add_entity(
        canonical_name="Higgs boson",
        entity_type=EntityType.THING,
        existence_status=ExistenceStatus.EXISTS,
        confidence=0.95,
        wikidata_qid="Q402",
        wikipedia_url="https://en.wikipedia.org/wiki/Higgs_boson",
        description="Elementary particle in the Standard Model of particle physics",
        source_type=SourceType.SCIENTIFIC,
        source_url="https://www.science.org/doi/10.1126/science.1232005",
        aliases=["Higgs particle", "God particle"]
    )
    
    # Add property for Higgs boson mass (from VERA Phase A example)
    service.add_property(
        entity_id=higgs.entity_id,
        property_name="mass",
        property_value="125.25",
        value_type="NUMBER",
        unit="GeV/c²",
        confidence=0.95
    )
    
    # Black swan - exists (counterexample from VERA)
    service.add_entity(
        canonical_name="Cygnus atratus",
        entity_type=EntityType.THING,
        existence_status=ExistenceStatus.EXISTS,
        confidence=0.99,
        wikidata_qid="Q35409",
        wikipedia_url="https://en.wikipedia.org/wiki/Black_swan",
        description="Large waterbird, a species of swan native to Australia",
        source_type=SourceType.WIKIDATA,
        source_url="https://www.wikidata.org/wiki/Q35409",
        aliases=["Black swan", "black swan"]
    )
    
    # Fictional entities - NOT_EXISTS
    unicorn = service.add_entity(
        canonical_name="Unicorn",
        entity_type=EntityType.FICTIONAL,
        existence_status=ExistenceStatus.NOT_EXISTS,
        confidence=0.99,
        wikidata_qid="Q19683",
        wikipedia_url="https://en.wikipedia.org/wiki/Unicorn",
        description="Legendary creature depicted as a horse with a horn",
        source_type=SourceType.WIKIDATA,
        source_url="https://www.wikidata.org/wiki/Q19683",
        aliases=["unicorns"]
    )
    
    pegasus = service.add_entity(
        canonical_name="Pegasus",
        entity_type=EntityType.MYTHOLOGICAL,
        existence_status=ExistenceStatus.NOT_EXISTS,
        confidence=0.99,
        wikidata_qid="Q188651",
        wikipedia_url="https://en.wikipedia.org/wiki/Pegasus",
        description="Mythical winged divine horse in Greek mythology",
        source_type=SourceType.WIKIDATA,
        source_url="https://www.wikidata.org/wiki/Q188651",
        aliases=["Πήγασος"]
    )
    
    sherlock = service.add_entity(
        canonical_name="Sherlock Holmes",
        entity_type=EntityType.FICTIONAL,
        existence_status=ExistenceStatus.NOT_EXISTS,
        confidence=0.99,
        wikidata_qid="Q4271",
        wikipedia_url="https://en.wikipedia.org/wiki/Sherlock_Holmes",
        description="Fictional detective created by Arthur Conan Doyle",
        source_type=SourceType.WIKIDATA,
        source_url="https://www.wikidata.org/wiki/Q4271",
        aliases=["Holmes", "The Great Detective"]
    )
    
    # Mythological entities
    zeus = service.add_entity(
        canonical_name="Zeus",
        entity_type=EntityType.MYTHOLOGICAL,
        existence_status=ExistenceStatus.NOT_EXISTS,
        confidence=0.99,
        wikidata_qid="Q34201",
        wikipedia_url="https://en.wikipedia.org/wiki/Zeus",
        description="Sky and thunder god in ancient Greek religion",
        source_type=SourceType.WIKIDATA,
        source_url="https://www.wikidata.org/wiki/Q34201",
        aliases=["Ζεύς", "Jupiter"]
    )
    
    # Places
    paris = service.add_entity(
        canonical_name="Paris",
        entity_type=EntityType.PLACE,
        existence_status=ExistenceStatus.EXISTS,
        confidence=0.99,
        wikidata_qid="Q90",
        wikipedia_url="https://en.wikipedia.org/wiki/Paris",
        description="Capital and largest city of France",
        source_type=SourceType.WIKIDATA,
        source_url="https://www.wikidata.org/wiki/Q90",
        aliases=["City of Light", "Paris, France"]
    )
    
    return {
        "socrates": socrates,
        "einstein": einstein,
        "higgs": higgs,
        "unicorn": unicorn,
        "pegasus": pegasus,
        "sherlock": sherlock,
        "zeus": zeus,
        "paris": paris
    }


# =============================================================================
# Test Suite
# =============================================================================

def run_test_suite():
    """Run comprehensive test suite for E! Verification Service."""
    print("=" * 70)
    print("V.E.R.A. E! Verification Service - Test Suite")
    print("=" * 70)
    print()
    
    # Initialize service with in-memory database
    service = EVerificationService(":memory:")
    
    # Seed test data
    print("Seeding test data...")
    entities = seed_test_data(service)
    
    stats = service.get_corpus_stats()
    print(f"Corpus loaded: {stats['total_entities']} entities, "
          f"{stats['total_aliases']} aliases, {stats['total_properties']} properties")
    print()
    
    passed = 0
    failed = 0
    
    test_cases = [
        # Existence checks - should find
        ("exists", "Socrates", ExistenceStatus.EXISTS, True),
        ("exists", "Albert Einstein", ExistenceStatus.EXISTS, True),
        ("exists", "Einstein", ExistenceStatus.EXISTS, True),  # Alias
        ("exists", "Higgs boson", ExistenceStatus.EXISTS, True),
        ("exists", "Black swan", ExistenceStatus.EXISTS, True),  # Alias for Cygnus atratus
        ("exists", "Paris", ExistenceStatus.EXISTS, True),
        
        # Existence checks - fictional/mythological (NOT_EXISTS)
        ("exists", "Unicorn", ExistenceStatus.NOT_EXISTS, True),
        ("exists", "unicorns", ExistenceStatus.NOT_EXISTS, True),  # Alias
        ("exists", "Pegasus", ExistenceStatus.NOT_EXISTS, True),
        ("exists", "Sherlock Holmes", ExistenceStatus.NOT_EXISTS, True),
        ("exists", "Zeus", ExistenceStatus.NOT_EXISTS, True),
        
        # Existence checks - not in corpus
        ("exists", "Xyzzy Foobar", ExistenceStatus.UNKNOWN, False),
        ("exists", "Professor Smith", ExistenceStatus.UNKNOWN, False),
    ]
    
    print("Existence Check Tests:")
    print("-" * 50)
    
    for test_type, query, expected_status, expected_found in test_cases:
        result = service.exists(query)
        
        status_match = result.existence_status == expected_status
        found_match = result.found_in_corpus == expected_found
        
        if status_match and found_match:
            passed += 1
            status = "✓ PASS"
        else:
            failed += 1
            status = "✗ FAIL"
        
        print(f"[{status}] exists(\"{query}\")")
        print(f"  Status: {result.existence_status.value} (expected: {expected_status.value}) {'✓' if status_match else '✗'}")
        print(f"  Found: {result.found_in_corpus} (expected: {expected_found}) {'✓' if found_match else '✗'}")
        if result.entity_id:
            print(f"  Entity ID: {result.entity_id}")
        print()
    
    # Identity resolution tests
    print("Identity Resolution Tests:")
    print("-" * 50)
    
    identity_tests = [
        ("Albert Einstein", "A. Einstein", IdentityRelationType.SAME_AS),
        ("Albert Einstein", "Einstein", IdentityRelationType.SAME_AS),
        ("Socrates", "Albert Einstein", IdentityRelationType.DIFFERENT),
        # D3 requires E!(x) ∧ E!(y) - since both are NOT_EXISTS, cannot apply D3
        ("Unicorn", "Pegasus", IdentityRelationType.UNKNOWN),
        ("Unknown Person A", "Unknown Person B", IdentityRelationType.UNKNOWN),
    ]
    
    for entity_a, entity_b, expected_relation in identity_tests:
        result = service.resolve_identity(entity_a, entity_b)
        
        relation_match = result.relation_type == expected_relation
        
        if relation_match:
            passed += 1
            status = "✓ PASS"
        else:
            failed += 1
            status = "✗ FAIL"
        
        print(f"[{status}] resolve_identity(\"{entity_a}\", \"{entity_b}\")")
        print(f"  Relation: {result.relation_type.value} (expected: {expected_relation.value}) {'✓' if relation_match else '✗'}")
        print(f"  NTP Symbol: {result.ntp_relation}")
        print(f"  Both Exist: {result.both_exist}")
        print()
    
    # Property retrieval test
    print("Property Retrieval Test:")
    print("-" * 50)
    
    higgs_result = service.exists("Higgs boson")
    if higgs_result.entity_id:
        props = service.get_properties(higgs_result.entity_id)
        mass_prop = next((p for p in props if p.property_name == "mass"), None)
        
        if mass_prop and mass_prop.property_value == "125.25":
            passed += 1
            print("[✓ PASS] get_properties(Higgs boson)")
            print(f"  Found mass: {mass_prop.property_value} {mass_prop.unit}")
        else:
            failed += 1
            print("[✗ FAIL] get_properties(Higgs boson)")
    else:
        failed += 1
        print("[✗ FAIL] Could not find Higgs boson for property test")
    
    print()
    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed out of {passed + failed} tests")
    print("=" * 70)
    
    service.close()
    return passed, failed


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    print()
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║     V.E.R.A. - Verified Existence and Reason Architecture        ║")
    print("║          E! Corpus & Verification Service v0.1.0                  ║")
    print("║                                                                    ║")
    print("║  Layer 2: Evidence-Based Existence Verification                   ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print()
    
    # Run test suite
    passed, failed = run_test_suite()
    
    # Demo usage
    print()
    print("=" * 70)
    print("Integration Demo: Full Verification Flow")
    print("=" * 70)
    print()
    
    service = EVerificationService(":memory:")
    seed_test_data(service)
    
    demo_queries = [
        "Does Socrates exist?",
        "What about unicorns?",
        "Is the Higgs boson real?",
        "Professor Smith from the university?"
    ]
    
    for query in demo_queries:
        # Extract entity name (simplified)
        name = query.replace("Does ", "").replace(" exist?", "")
        name = name.replace("What about ", "").replace("?", "")
        name = name.replace("Is the ", "").replace(" real", "")
        name = name.strip()
        
        result = service.exists(name)
        
        print(f"Query: \"{query}\"")
        print(f"  Entity: {result.canonical_name}")
        print(f"  Status: {result.existence_status.value}")
        print(f"  Confidence: {result.confidence:.2f}")
        print(f"  In Corpus: {result.found_in_corpus}")
        
        if result.existence_status == ExistenceStatus.EXISTS:
            print(f"  → Predication ALLOWED (E! verified)")
        elif result.existence_status == ExistenceStatus.NOT_EXISTS:
            print(f"  → Predication allowed but VACUOUS (~E! confirmed)")
        else:
            print(f"  → Predication BLOCKED (E! unknown - would hallucinate)")
        print()
    
    service.close()
    
    print("=" * 70)
    print("Interactive Usage:")
    print("  from e_corpus import EVerificationService, seed_test_data")
    print("  service = EVerificationService('vera_corpus.db')")
    print("  seed_test_data(service)")
    print("  result = service.exists('Socrates')")
    print("  print(result.existence_status)  # → EXISTS")
    print("=" * 70)
