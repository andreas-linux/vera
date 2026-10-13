#!/usr/bin/env python3
"""
V.E.R.A. demo: hallucination prevention in action.

Runs a handful of statements through the full pipeline against the built-in
demonstration corpus and shows which are allowed, which are blocked, and why.

    python examples/demo_basic.py
"""

from vera import VERAPipeline, VerificationOutcome

STATEMENTS = [
    # n-type: no existence presupposition, so no E! check is needed
    "All swans are white.",
    # e-type, subject in the corpus and EXISTS: allowed
    "Socrates is mortal.",
    "Aspirin is an analgesic.",
    # e-type, subject confirmed NOT to exist: blocked
    "Sherlock Holmes is a detective.",
    # e-type, subject unknown to the corpus: blocked (fail-safe refusal)
    "Zarkonite is a rare mineral.",
]

ACTION = {
    VerificationOutcome.VERIFIED: "ALLOWED",
    VerificationOutcome.NO_CHECK_REQUIRED: "ALLOWED (n-type)",
    VerificationOutcome.NOT_EXISTS: "BLOCKED (does not exist)",
    VerificationOutcome.REFUSAL: "BLOCKED (existence unverified)",
}


def main() -> None:
    pipeline = VERAPipeline()
    try:
        for statement in STATEMENTS:
            r = pipeline.run(statement)
            print(f'"{statement}"')
            print(f"   {ACTION.get(r.outcome, r.outcome.value)}")
            for er in r.existence_results:
                print(f"   E!({er.entity_name}) = {er.existence_status.value}")
            print()
    finally:
        pipeline.close()


if __name__ == "__main__":
    main()
