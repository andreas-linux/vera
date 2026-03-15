"""
V.E.R.A. Pipeline
==================
Full Triple-Layer Verification System

Integrates all three verification layers into a single query pipeline:
    Layer 1: Krampitz Load Analyzer    -- determines e/n characteristic
    Layer 2: E! Verification Service   -- verifies entity existence
    Layer 3: D-Service (stub)          -- resolves identity (v0.2)

This module also handles:
    - Natural language parsing (via FormulaParser)
    - Audit trail generation (every reasoning step logged)
    - Fail-safe refusal (REF-001) when existence cannot be verified

Architecture:
    User Query (NL)
        --> FormulaParser     (NL to NTP formula)
        --> KrampitzAnalyzer  (Layer 1: e or n?)
        --> EVerificationService (Layer 2: EXISTS / NOT_EXISTS / UNKNOWN)
        --> DService stub     (Layer 3: identity resolution)
        --> VerifiedResponse  (with full audit trail)

Author: V.E.R.A. Open Source Initiative
Version: 0.1.0
Date: March 2026
"""

import uuid
import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime

from krampitz_analyzer import KrampitzAnalyzer, Characteristic
from formula_parser import FormulaParser, ParseStatus
from e_verification_service import EVerificationService, ExistenceStatus, ExistenceResult


# =============================================================================
# Response Types
# =============================================================================

class VerificationOutcome(Enum):
    """Final verdict of the pipeline."""
    VERIFIED = "VERIFIED"             # All e-type subjects confirmed EXISTS
    REFUSAL = "REFUSAL"               # Fail-safe: one or more subjects UNKNOWN
    NOT_EXISTS = "NOT_EXISTS"         # Subject confirmed NOT_EXISTS (fictional etc.)
    NO_CHECK_REQUIRED = "NO_CHECK_REQUIRED"  # Formula is n-type; no E! check needed
    PARSE_FAILED = "PARSE_FAILED"     # Could not parse input
    ERROR = "ERROR"


@dataclass
class AuditStep:
    """One step in the pipeline audit trail."""
    step_number: int
    layer: str
    action: str
    input_value: str
    output_value: str
    rule_applied: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class VerifiedResponse:
    """
    The output of a full VERA pipeline run.

    Contains:
    - The final outcome (VERIFIED / REFUSAL / NOT_EXISTS / NO_CHECK_REQUIRED)
    - Subject existence results for every entity in the query
    - Complete audit trail (every reasoning step)
    - A human-readable summary
    """
    run_id: str
    query: str
    outcome: VerificationOutcome
    characteristic: Optional[str]          # 'e' or 'n'
    subjects: List[str]
    existence_results: List[ExistenceResult]
    audit_trail: List[AuditStep]
    summary: str
    error_code: Optional[str] = None
    processing_time_ms: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "query": self.query,
            "outcome": self.outcome.value,
            "characteristic": self.characteristic,
            "subjects": self.subjects,
            "existence_results": [r.to_dict() for r in self.existence_results],
            "audit_trail": [
                {
                    "step": s.step_number,
                    "layer": s.layer,
                    "action": s.action,
                    "input": s.input_value,
                    "output": s.output_value,
                    "rule": s.rule_applied,
                    "timestamp": s.timestamp,
                }
                for s in self.audit_trail
            ],
            "summary": self.summary,
            "error_code": self.error_code,
            "processing_time_ms": self.processing_time_ms,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def print_audit_trail(self) -> None:
        """Print a human-readable audit trail."""
        print(f"\nAudit Trail -- Run ID: {self.run_id}")
        print("-" * 60)
        for step in self.audit_trail:
            print(f"  Step {step.step_number} [{step.layer}]  {step.action}")
            print(f"    In:  {step.input_value}")
            print(f"    Out: {step.output_value}")
            if step.rule_applied:
                print(f"    Rule: {step.rule_applied}")
        print("-" * 60)


# =============================================================================
# D-Service Stub (Layer 3 -- v0.2)
# =============================================================================

class DServiceStub:
    """
    Stub implementation of the D-Service (Layer 3).

    Full implementation deferred to v0.2. This stub passes identity
    checks through without resolution, logging the gap explicitly.

    NTP Basis:
        D1: Weak Distinguishability    (x#y)    -- at least one exists
        D2: Weak Indiscernibility      (~(x#y)) -- equivalence relation
        D3: Strong Distinguishability  (x != y) -- both must exist
        D4: Strong Indiscernibility    (~(x != y)) -- context-sensitive
    """

    def resolve(self, entity_a: str, entity_b: str) -> Dict[str, Any]:
        return {
            "relation_type": "UNKNOWN",
            "ntp_relation": "unresolved",
            "confidence": 0.0,
            "note": "D-Service identity resolution not yet implemented (v0.2 milestone).",
            "entity_a": entity_a,
            "entity_b": entity_b,
        }


# =============================================================================
# VERA Pipeline
# =============================================================================

class VERAPipeline:
    """
    The full V.E.R.A. triple-layer verification pipeline.

    Takes a natural language query and returns a VerifiedResponse with:
    - Existence verification for every entity subject
    - Full NTP rule chain trace
    - Immutable audit trail
    - Fail-safe refusal when existence is unverifiable

    Usage:
        pipeline = VERAPipeline()
        response = pipeline.run("Aspirin is an analgesic.")
        print(response.outcome)         # VerificationOutcome.VERIFIED
        print(response.summary)
        response.print_audit_trail()
    """

    def __init__(self, db_path: str = ":memory:"):
        self.parser = FormulaParser()
        self.krampitz = KrampitzAnalyzer()
        self.e_service = EVerificationService(db_path=db_path)
        self.d_service = DServiceStub()

    def run(self, query: str) -> VerifiedResponse:
        """
        Execute the full verification pipeline for a natural language query.

        Pipeline steps:
            1. Parse NL to NTP formula
            2. Determine existential loading (Krampitz, Layer 1)
            3. If e-type: verify each subject entity (E! Service, Layer 2)
            4. Apply fail-safe refusal if any subject is UNKNOWN
            5. Return VerifiedResponse with full audit trail

        Args:
            query: Natural language statement to verify.

        Returns:
            VerifiedResponse with outcome and complete audit trail.
        """
        run_id = str(uuid.uuid4())[:8]
        start = datetime.utcnow()
        audit: List[AuditStep] = []
        step = 0

        # ----------------------------------------------------------------
        # Step 1: Parse natural language
        # ----------------------------------------------------------------
        step += 1
        parse_result = self.parser.parse(query)
        audit.append(AuditStep(
            step_number=step,
            layer="FormulaParser",
            action="Parse natural language to NTP formula",
            input_value=query,
            output_value=str(parse_result.formula) if parse_result.formula else f"FAILED ({parse_result.status.name})",
        ))

        if parse_result.status == ParseStatus.FAILED or parse_result.formula is None:
            return self._error_response(run_id, query, audit, start,
                                        "VERA-005", "Could not parse query into NTP formula.")

        subjects = parse_result.subjects
        audit.append(AuditStep(
            step_number=step,
            layer="FormulaParser",
            action="Extract subject terms",
            input_value=str(parse_result.formula),
            output_value=f"Subjects: {subjects}  |  Statement type: {parse_result.statement_type.name}",
        ))

        # ----------------------------------------------------------------
        # Step 2: Krampitz analysis (Layer 1)
        # ----------------------------------------------------------------
        step += 1
        krampitz_result = self.krampitz.analyze(parse_result.formula)
        characteristic = krampitz_result.characteristic
        audit.append(AuditStep(
            step_number=step,
            layer="KrampitzAnalyzer (Layer 1)",
            action="Determine existential loading",
            input_value=str(parse_result.formula),
            output_value=f"Characteristic: {characteristic.value}  |  Requires E! check: {krampitz_result.requires_existence_check}",
            rule_applied=" -> ".join(krampitz_result.rule_chain),
        ))

        # ----------------------------------------------------------------
        # Step 3: If n-type, no existence check required
        # ----------------------------------------------------------------
        if characteristic == Characteristic.N:
            summary = (
                f"Formula '{parse_result.formula}' is n-type (no existence presupposition). "
                f"No E! verification required. Statement is logically valid regardless of "
                f"whether subjects exist."
            )
            elapsed = (datetime.utcnow() - start).total_seconds() * 1000
            return VerifiedResponse(
                run_id=run_id,
                query=query,
                outcome=VerificationOutcome.NO_CHECK_REQUIRED,
                characteristic=characteristic.value,
                subjects=subjects,
                existence_results=[],
                audit_trail=audit,
                summary=summary,
                processing_time_ms=round(elapsed, 2),
            )

        # ----------------------------------------------------------------
        # Step 4: E! Verification (Layer 2) -- for each subject
        # ----------------------------------------------------------------
        existence_results: List[ExistenceResult] = []
        unverified: List[str] = []
        nonexistent: List[str] = []

        for subject in subjects:
            step += 1
            e_result = self.e_service.check_existence(subject, pipeline_run_id=run_id)
            existence_results.append(e_result)

            audit.append(AuditStep(
                step_number=step,
                layer="EVerificationService (Layer 2)",
                action=f"Check existence of '{subject}'",
                input_value=subject,
                output_value=(
                    f"{e_result.existence_status.value}  |  "
                    f"Canonical: '{e_result.canonical_name or 'n/a'}'  |  "
                    f"Confidence: {e_result.confidence:.2f}"
                ),
                rule_applied="IF-002 E! Corpus lookup",
            ))

            if e_result.existence_status == ExistenceStatus.UNKNOWN:
                unverified.append(subject)
            elif e_result.existence_status == ExistenceStatus.NOT_EXISTS:
                nonexistent.append(subject)

        # ----------------------------------------------------------------
        # Step 5: Determine final outcome
        # ----------------------------------------------------------------
        step += 1
        elapsed = (datetime.utcnow() - start).total_seconds() * 1000

        if nonexistent:
            outcome = VerificationOutcome.NOT_EXISTS
            summary = (
                f"EXISTENCE FIREWALL: The subject(s) {nonexistent} are confirmed NOT to exist "
                f"in the E! Corpus. Any predication about a non-existent entity is a hallucination "
                f"under NTP. Query rejected."
            )
            audit.append(AuditStep(
                step_number=step,
                layer="VERAPipeline",
                action="Apply existence-predication firewall",
                input_value=f"NOT_EXISTS subjects: {nonexistent}",
                output_value="REJECTED -- subject does not exist",
                rule_applied="NTP Architecture Principle 1: Wall of Separation",
            ))

        elif unverified:
            outcome = VerificationOutcome.REFUSAL
            summary = (
                f"FAIL-SAFE REFUSAL (REF-001): The subject(s) {unverified} could not be verified "
                f"in the E! Corpus. V.E.R.A. cannot assert properties about entities whose "
                f"existence is unconfirmed. Integrity over answers."
            )
            audit.append(AuditStep(
                step_number=step,
                layer="VERAPipeline",
                action="Apply fail-safe refusal (REF-001)",
                input_value=f"UNKNOWN subjects: {unverified}",
                output_value="REFUSAL -- existence unverifiable",
                rule_applied="REF-001: Fail-Safe Refusal",
            ))

        else:
            outcome = VerificationOutcome.VERIFIED
            verified_names = [r.canonical_name for r in existence_results if r.canonical_name]
            summary = (
                f"VERIFIED: All subjects {verified_names} confirmed to exist in the E! Corpus. "
                f"Formula characteristic: {characteristic.value}. "
                f"Predication is grounded in verified existence."
            )
            audit.append(AuditStep(
                step_number=step,
                layer="VERAPipeline",
                action="Confirm verification",
                input_value=f"All subjects: {subjects}",
                output_value=f"VERIFIED -- existence confirmed for all subjects",
                rule_applied="NTP: E! precedes M (predication follows verified existence)",
            ))

        return VerifiedResponse(
            run_id=run_id,
            query=query,
            outcome=outcome,
            characteristic=characteristic.value,
            subjects=subjects,
            existence_results=existence_results,
            audit_trail=audit,
            summary=summary,
            processing_time_ms=round(elapsed, 2),
        )

    def close(self) -> None:
        self.e_service.close()

    # ----------------------------------------------------------------
    # Private helpers
    # ----------------------------------------------------------------

    def _error_response(
        self,
        run_id: str,
        query: str,
        audit: List[AuditStep],
        start: datetime,
        error_code: str,
        message: str,
    ) -> VerifiedResponse:
        elapsed = (datetime.utcnow() - start).total_seconds() * 1000
        return VerifiedResponse(
            run_id=run_id,
            query=query,
            outcome=VerificationOutcome.ERROR,
            characteristic=None,
            subjects=[],
            existence_results=[],
            audit_trail=audit,
            summary=message,
            error_code=error_code,
            processing_time_ms=round(elapsed, 2),
        )


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    print()
    print("=" * 70)
    print("  V.E.R.A. -- Triple-Layer Verification Pipeline v0.1.0")
    print("  'Truth is a feature, not an option.'")
    print("=" * 70)

    pipeline = VERAPipeline()

    demo_queries = [
        "Aspirin is an analgesic.",
        "Sherlock Holmes is a detective.",
        "All swans are white.",
        "Zarkonite is a rare mineral.",
        "Socrates is mortal.",
    ]

    for query in demo_queries:
        print(f"\nQuery: '{query}'")
        response = pipeline.run(query)
        print(f"Outcome:    {response.outcome.value}")
        print(f"Char:       {response.characteristic or 'N/A'}")
        print(f"Subjects:   {response.subjects}")
        print(f"Summary:    {response.summary[:100]}...")
        print(f"Time:       {response.processing_time_ms}ms")

    pipeline.close()
