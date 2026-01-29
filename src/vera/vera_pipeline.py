"""
V.E.R.A. Integrated Verification Pipeline
==========================================
Complete Triple-Layer Verification System

This module integrates all V.E.R.A. components into a unified pipeline:
- Layer 1: Krampitz Load Analyzer (R1-R9 existential loading)
- Layer 2: E! Verification Service (existence checking)
- Layer 3: D-Service (identity resolution via D1-D4)

The pipeline implements the Query Processing Pipeline from 
VERA_Process_Architecture_v1.0, providing end-to-end verification
of natural language statements.

Author: V.E.R.A. Open Source Initiative
Version: 0.1.0 (Prototype)
Date: January 2026
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime
import json

# Import V.E.R.A. components
from krampitz_analyzer import (
    KrampitzAnalyzer, Formula, Characteristic, AnalysisResult
)
from formula_parser import (
    FormulaParser, ParseResult, ParseStatus, StatementType, NTPPipeline
)
from e_corpus import (
    EVerificationService, ExistenceStatus, ExistenceResult,
    IdentityRelationType, IdentityResult, seed_test_data
)


# =============================================================================
# Verification Result Types
# =============================================================================

class VerificationStatus(Enum):
    """Final verification status for a statement."""
    VERIFIED = "VERIFIED"        # All subjects exist, predication allowed
    REFUSED = "REFUSED"          # Subject does not exist, cannot predicate
    UNCERTAIN = "UNCERTAIN"      # Subject existence unknown, proceed with caution
    VACUOUS = "VACUOUS"          # Subject doesn't exist but statement type allows (universals)
    SKIPPED = "SKIPPED"          # n-type formula, no E! check needed
    PARSE_ERROR = "PARSE_ERROR"  # Could not parse input


@dataclass
class SubjectVerification:
    """Verification result for a single subject."""
    subject_name: str
    existence_status: ExistenceStatus
    entity_id: Optional[str]
    confidence: float
    found_in_corpus: bool


@dataclass
class VerificationResult:
    """Complete verification result for a statement."""
    # Input
    original_text: str
    
    # Parse result
    parse_status: ParseStatus
    statement_type: StatementType
    formula: Optional[str]
    
    # Krampitz analysis
    characteristic: Optional[Characteristic]
    rule_chain: List[str]
    requires_existence_check: bool
    
    # E! Verification
    verification_status: VerificationStatus
    subject_verifications: List[SubjectVerification]
    
    # Audit trail
    timestamp: str
    reasoning_chain: List[str]
    warnings: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_text": self.original_text,
            "parse_status": self.parse_status.name,
            "statement_type": self.statement_type.name,
            "formula": self.formula,
            "characteristic": self.characteristic.value if self.characteristic else None,
            "rule_chain": self.rule_chain,
            "requires_existence_check": self.requires_existence_check,
            "verification_status": self.verification_status.value,
            "subject_verifications": [
                {
                    "subject": sv.subject_name,
                    "status": sv.existence_status.value,
                    "confidence": sv.confidence,
                    "found": sv.found_in_corpus
                } for sv in self.subject_verifications
            ],
            "timestamp": self.timestamp,
            "reasoning_chain": self.reasoning_chain,
            "warnings": self.warnings
        }
    
    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
    
    def get_human_readable_result(self) -> str:
        """Generate a human-readable explanation of the verification."""
        lines = []
        lines.append(f"Statement: \"{self.original_text}\"")
        lines.append(f"Formula: {self.formula}")
        lines.append(f"Characteristic: {self.characteristic.value if self.characteristic else 'N/A'} ({self._explain_characteristic()})")
        lines.append(f"Verification: {self.verification_status.value}")
        lines.append("")
        lines.append("Reasoning Chain:")
        for i, step in enumerate(self.reasoning_chain, 1):
            lines.append(f"  {i}. {step}")
        
        if self.warnings:
            lines.append("")
            lines.append("Warnings:")
            for w in self.warnings:
                lines.append(f"  ⚠ {w}")
        
        return "\n".join(lines)
    
    def _explain_characteristic(self) -> str:
        if self.characteristic == Characteristic.E:
            return "existentially loaded - requires subjects to exist"
        elif self.characteristic == Characteristic.N:
            return "not existentially loaded - no existence requirement"
        return "unknown"


# =============================================================================
# V.E.R.A. Integrated Pipeline
# =============================================================================

class VERAPipeline:
    """
    V.E.R.A. Integrated Verification Pipeline
    
    Implements the complete triple-layer verification flow:
    
    1. Parse natural language → NTP formula (Formula Parser)
    2. Analyze formula → existential loading (Krampitz Analyzer)
    3. If e-type, verify subjects exist (E! Verification Service)
    4. Return verified result with complete reasoning chain
    
    This is the core engine that prevents hallucination by enforcing
    NTP Rule R1: Elementary predicates require subject existence.
    """
    
    def __init__(self, corpus_db_path: str = ":memory:", seed_data: bool = True):
        """
        Initialize the V.E.R.A. pipeline.
        
        Args:
            corpus_db_path: Path to E! Corpus database
            seed_data: Whether to seed test data (for demo/testing)
        """
        # Initialize components
        self.parser = FormulaParser()
        self.analyzer = KrampitzAnalyzer()
        self.e_service = EVerificationService(corpus_db_path)
        
        # Optionally seed test data
        if seed_data:
            seed_test_data(self.e_service)
    
    def verify(self, text: str) -> VerificationResult:
        """
        Verify a natural language statement through the complete pipeline.
        
        This implements the 10-step Query Processing Pipeline from
        VERA_Process_Architecture_v1.0.
        
        Args:
            text: Natural language statement to verify
            
        Returns:
            VerificationResult with complete analysis and reasoning chain
        """
        timestamp = datetime.utcnow().isoformat()
        reasoning_chain = []
        warnings = []
        
        # Step 1: Parse natural language to NTP formula
        reasoning_chain.append(f"Received input: \"{text}\"")
        parse_result = self.parser.parse(text)
        
        if parse_result.status == ParseStatus.FAILED:
            reasoning_chain.append("PARSE FAILED: Could not convert to NTP formula")
            return VerificationResult(
                original_text=text,
                parse_status=parse_result.status,
                statement_type=parse_result.statement_type,
                formula=None,
                characteristic=None,
                rule_chain=[],
                requires_existence_check=False,
                verification_status=VerificationStatus.PARSE_ERROR,
                subject_verifications=[],
                timestamp=timestamp,
                reasoning_chain=reasoning_chain,
                warnings=parse_result.warnings
            )
        
        reasoning_chain.append(f"Parsed to formula: {parse_result.formula}")
        reasoning_chain.append(f"Statement type: {parse_result.statement_type.name}")
        warnings.extend(parse_result.warnings)
        
        # Step 2: Analyze existential loading (Krampitz Rules R1-R9)
        krampitz_result = self.analyzer.analyze(parse_result.formula)
        
        reasoning_chain.append(f"Krampitz analysis: characteristic = {krampitz_result.characteristic.value}")
        reasoning_chain.append(f"Rule chain applied: {' → '.join(krampitz_result.rule_chain)}")
        
        # Step 3: Determine if E! verification is needed
        if krampitz_result.characteristic == Characteristic.N:
            # n-type: No existence requirement
            reasoning_chain.append("Formula is n-type (not existentially loaded)")
            reasoning_chain.append("No existence verification required - statement is safe")
            
            return VerificationResult(
                original_text=text,
                parse_status=parse_result.status,
                statement_type=parse_result.statement_type,
                formula=str(parse_result.formula),
                characteristic=krampitz_result.characteristic,
                rule_chain=krampitz_result.rule_chain,
                requires_existence_check=False,
                verification_status=VerificationStatus.SKIPPED,
                subject_verifications=[],
                timestamp=timestamp,
                reasoning_chain=reasoning_chain,
                warnings=warnings
            )
        
        # e-type: Must verify subjects exist
        reasoning_chain.append("Formula is e-type (existentially loaded)")
        reasoning_chain.append("Existence verification REQUIRED per NTP Rule R1")
        
        # Step 4: Extract and verify subjects
        subjects = parse_result.subjects
        reasoning_chain.append(f"Subjects to verify: {subjects}")
        
        subject_verifications = []
        all_exist = True
        any_not_exist = False
        any_unknown = False
        
        for subject in subjects:
            e_result = self.e_service.exists(subject)
            
            sv = SubjectVerification(
                subject_name=subject,
                existence_status=e_result.existence_status,
                entity_id=e_result.entity_id,
                confidence=e_result.confidence,
                found_in_corpus=e_result.found_in_corpus
            )
            subject_verifications.append(sv)
            
            if e_result.existence_status == ExistenceStatus.EXISTS:
                reasoning_chain.append(f"  E!({subject}) = EXISTS ✓ (confidence: {e_result.confidence:.2f})")
            elif e_result.existence_status == ExistenceStatus.NOT_EXISTS:
                reasoning_chain.append(f"  E!({subject}) = NOT_EXISTS ✗ (confirmed fictional/mythological)")
                any_not_exist = True
                all_exist = False
            else:
                reasoning_chain.append(f"  E!({subject}) = UNKNOWN ⚠ (not in E! Corpus)")
                any_unknown = True
                all_exist = False
        
        # Step 5: Determine final verification status
        if all_exist:
            verification_status = VerificationStatus.VERIFIED
            reasoning_chain.append("All subjects verified to exist")
            reasoning_chain.append("PREDICATION ALLOWED - statement may proceed")
        elif any_not_exist:
            # Check if this is a universal statement (vacuously true is OK)
            if parse_result.statement_type in (StatementType.UNIVERSAL_AFFIRMATIVE, 
                                                StatementType.UNIVERSAL_NEGATIVE):
                verification_status = VerificationStatus.VACUOUS
                reasoning_chain.append("Subject confirmed not to exist, but universal statement")
                reasoning_chain.append("VACUOUSLY TRUE - predication allowed but empty domain")
            else:
                verification_status = VerificationStatus.REFUSED
                reasoning_chain.append("Subject confirmed not to exist")
                reasoning_chain.append("PREDICATION REFUSED - would assert about non-existent entity")
        else:
            verification_status = VerificationStatus.UNCERTAIN
            reasoning_chain.append("Subject existence unknown (not in E! Corpus)")
            reasoning_chain.append("UNCERTAIN - proceed with qualification or refuse")
            warnings.append("Entity not found in E! Corpus - existence cannot be verified")
        
        return VerificationResult(
            original_text=text,
            parse_status=parse_result.status,
            statement_type=parse_result.statement_type,
            formula=str(parse_result.formula),
            characteristic=krampitz_result.characteristic,
            rule_chain=krampitz_result.rule_chain,
            requires_existence_check=True,
            verification_status=verification_status,
            subject_verifications=subject_verifications,
            timestamp=timestamp,
            reasoning_chain=reasoning_chain,
            warnings=warnings
        )
    
    def resolve_identity(self, entity_a: str, entity_b: str) -> IdentityResult:
        """
        Resolve identity between two entity references.
        
        Delegates to D-Service (E! Verification Service identity resolution).
        
        Args:
            entity_a: First entity name
            entity_b: Second entity name
            
        Returns:
            IdentityResult with NTP relation (D1-D4)
        """
        return self.e_service.resolve_identity(entity_a, entity_b)
    
    def get_corpus_stats(self) -> Dict[str, Any]:
        """Get statistics about the E! Corpus."""
        return self.e_service.get_corpus_stats()
    
    def close(self):
        """Close database connections."""
        self.e_service.close()


# =============================================================================
# Test Suite
# =============================================================================

def run_integration_tests():
    """Run comprehensive integration tests for the full pipeline."""
    print("=" * 70)
    print("V.E.R.A. Integrated Pipeline - Integration Test Suite")
    print("=" * 70)
    print()
    
    pipeline = VERAPipeline(":memory:", seed_data=True)
    
    stats = pipeline.get_corpus_stats()
    print(f"E! Corpus loaded: {stats['total_entities']} entities")
    print()
    
    test_cases = [
        # n-type statements (no E! check needed)
        {
            "input": "All swans are white",
            "expected_status": VerificationStatus.SKIPPED,
            "expected_char": Characteristic.N,
            "description": "Universal affirmative - n-type, no E! check"
        },
        {
            "input": "No fish are mammals",
            "expected_status": VerificationStatus.SKIPPED,
            "expected_char": Characteristic.N,
            "description": "Universal negative - n-type, no E! check"
        },
        
        # e-type with existing subject
        {
            "input": "Socrates is mortal",
            "expected_status": VerificationStatus.VERIFIED,
            "expected_char": Characteristic.E,
            "description": "Singular affirmative - subject EXISTS"
        },
        {
            "input": "Albert Einstein is a physicist",
            "expected_status": VerificationStatus.VERIFIED,
            "expected_char": Characteristic.E,
            "description": "Singular affirmative - subject EXISTS (via alias)"
        },
        {
            "input": "The Higgs boson is an elementary particle",
            "expected_status": VerificationStatus.VERIFIED,
            "expected_char": Characteristic.E,
            "description": "Singular affirmative - verified scientific entity"
        },
        
        # e-type with non-existing subject (fictional)
        {
            "input": "Unicorns have magical powers",
            "expected_status": VerificationStatus.REFUSED,
            "expected_char": Characteristic.E,
            "description": "Singular affirmative - subject NOT_EXISTS (fictional)"
        },
        {
            "input": "Sherlock Holmes lives in London",
            "expected_status": VerificationStatus.REFUSED,
            "expected_char": Characteristic.E,
            "description": "Singular affirmative - subject NOT_EXISTS (fictional)"
        },
        
        # e-type with unknown subject (potential hallucination)
        {
            "input": "Professor Smith published a paper",
            "expected_status": VerificationStatus.UNCERTAIN,
            "expected_char": Characteristic.E,
            "description": "Singular affirmative - subject UNKNOWN (would hallucinate)"
        },
        {
            "input": "The XYZ Corporation announced earnings",
            "expected_status": VerificationStatus.UNCERTAIN,
            "expected_char": Characteristic.E,
            "description": "Singular affirmative - subject UNKNOWN (would hallucinate)"
        },
        
        # Existence claims
        {
            "input": "Does the Higgs boson exist?",
            "expected_status": VerificationStatus.VERIFIED,
            "expected_char": Characteristic.E,
            "description": "Existence claim - subject EXISTS"
        },
        {
            "input": "Unicorns exist",
            "expected_status": VerificationStatus.REFUSED,
            "expected_char": Characteristic.E,
            "description": "Existence claim - subject NOT_EXISTS"
        },
        
        # Particular statements (existentially loaded)
        {
            "input": "Some birds are black",
            "expected_status": VerificationStatus.UNCERTAIN,
            "expected_char": Characteristic.E,
            "description": "Particular affirmative - class not verified"
        },
    ]
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        result = pipeline.verify(test["input"])
        
        status_match = result.verification_status == test["expected_status"]
        char_match = result.characteristic == test["expected_char"]
        
        if status_match and char_match:
            passed += 1
            status = "✓ PASS"
        else:
            failed += 1
            status = "✗ FAIL"
        
        print(f"[{status}] {test['description']}")
        print(f"  Input: \"{test['input']}\"")
        print(f"  Formula: {result.formula}")
        print(f"  Characteristic: {result.characteristic.value if result.characteristic else 'N/A'} (expected: {test['expected_char'].value}) {'✓' if char_match else '✗'}")
        print(f"  Status: {result.verification_status.value} (expected: {test['expected_status'].value}) {'✓' if status_match else '✗'}")
        if result.subject_verifications:
            for sv in result.subject_verifications:
                print(f"    Subject '{sv.subject_name}': {sv.existence_status.value}")
        print()
    
    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("=" * 70)
    
    pipeline.close()
    return passed, failed


def run_demo():
    """Run interactive demonstration of the V.E.R.A. pipeline."""
    print()
    print("=" * 70)
    print("V.E.R.A. Pipeline - Hallucination Prevention Demo")
    print("=" * 70)
    print()
    
    pipeline = VERAPipeline(":memory:", seed_data=True)
    
    demo_statements = [
        "All swans are white",
        "Socrates is mortal",
        "Some unicorns have golden horns",
        "Professor Smith from MIT published a groundbreaking paper",
        "The Higgs boson has a mass of 125 GeV",
        "Zeus lives on Mount Olympus",
    ]
    
    for statement in demo_statements:
        print(f"{'='*60}")
        result = pipeline.verify(statement)
        print(result.get_human_readable_result())
        print()
    
    # Demo: Identity resolution
    print("=" * 60)
    print("Identity Resolution Demo (D-Service)")
    print("=" * 60)
    print()
    
    identity_tests = [
        ("Albert Einstein", "A. Einstein"),
        ("Albert Einstein", "Socrates"),
        ("Unicorn", "Pegasus"),
    ]
    
    for entity_a, entity_b in identity_tests:
        result = pipeline.resolve_identity(entity_a, entity_b)
        print(f"resolve_identity(\"{entity_a}\", \"{entity_b}\")")
        print(f"  Relation: {result.relation_type.value}")
        print(f"  NTP Symbol: {result.ntp_relation}")
        print(f"  Both Exist: {result.both_exist}")
        print()
    
    pipeline.close()


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    print()
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║     V.E.R.A. - Verified Existence and Reason Architecture        ║")
    print("║              Integrated Verification Pipeline v0.1.0              ║")
    print("║                                                                    ║")
    print("║  'Truth is a feature, not an option.'                             ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print()
    
    # Run integration tests
    passed, failed = run_integration_tests()
    
    # Run demo
    run_demo()
    
    print("=" * 70)
    print("V.E.R.A. Pipeline Ready")
    print()
    print("Usage:")
    print("  from vera_pipeline import VERAPipeline")
    print("  pipeline = VERAPipeline('corpus.db')")
    print("  result = pipeline.verify('Socrates is mortal')")
    print("  print(result.verification_status)  # → VERIFIED")
    print("=" * 70)
