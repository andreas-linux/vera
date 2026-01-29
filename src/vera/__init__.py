"""
V.E.R.A. - Verified Existence and Reason Architecture
======================================================

A triple-layer verification system for preventing AI hallucination
using Non-Traditional Predication Theory (NTP).

Core Components:
    - KrampitzAnalyzer: Layer 1 - Existential loading analysis (R1-R9)
    - FormulaParser: Natural language to NTP formula conversion
    - EVerificationService: Layer 2 - E! Corpus existence verification
    - VERAPipeline: Integrated verification pipeline

Basic Usage:
    >>> from vera import VERAPipeline
    >>> pipeline = VERAPipeline()
    >>> result = pipeline.verify("Socrates is mortal")
    >>> print(result.verification_status)
    VERIFIED

Theory:
    V.E.R.A. implements NTP as developed by Prof. Dr. Horst Wessel
    at Humboldt University Berlin (1991-1996). The key insight is that
    predication (ℳ) must be separated from existence (E!), preventing
    AI systems from asserting facts about entities that don't exist.

License:
    MIT License - See LICENSE file for details.

Copyright:
    (c) 2026 V.E.R.A. Open Source Initiative
"""

__version__ = "0.1.0"
__author__ = "Andreas Hamberger"
__license__ = "MIT"

# Core imports
from .krampitz_analyzer import (
    KrampitzAnalyzer,
    Characteristic,
    Formula,
    Predicate,
    Negation,
    InnerNegation,
    Conjunction,
    Disjunction,
    Implication,
    Biconditional,
    Universal,
    Existential,
    AnalysisResult,
)

from .formula_parser import (
    FormulaParser,
    NTPPipeline,
    ParseResult,
    ParseStatus,
    StatementType,
)

from .e_corpus import (
    EVerificationService,
    ECorpusSchema,
    ExistenceStatus,
    EntityType,
    SourceType,
    Entity,
    Provenance,
    Property,
    ExistenceResult,
    IdentityResult,
    IdentityRelationType,
    seed_test_data,
)

from .vera_pipeline import (
    VERAPipeline,
    VerificationResult,
    VerificationStatus,
    SubjectVerification,
)

__all__ = [
    # Version info
    "__version__",
    "__author__",
    "__license__",
    
    # Layer 1: Krampitz Analyzer
    "KrampitzAnalyzer",
    "Characteristic",
    "Formula",
    "Predicate",
    "Negation",
    "InnerNegation",
    "Conjunction",
    "Disjunction",
    "Implication",
    "Biconditional",
    "Universal",
    "Existential",
    "AnalysisResult",
    
    # Formula Parser
    "FormulaParser",
    "NTPPipeline",
    "ParseResult",
    "ParseStatus",
    "StatementType",
    
    # Layer 2: E! Corpus
    "EVerificationService",
    "ECorpusSchema",
    "ExistenceStatus",
    "EntityType",
    "SourceType",
    "Entity",
    "Provenance",
    "Property",
    "ExistenceResult",
    "IdentityResult",
    "IdentityRelationType",
    "seed_test_data",
    
    # Integrated Pipeline
    "VERAPipeline",
    "VerificationResult",
    "VerificationStatus",
    "SubjectVerification",
]
