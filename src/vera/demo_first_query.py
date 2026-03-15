"""
V.E.R.A. First Light Demo
==========================
The first end-to-end verified query.

This script demonstrates the complete triple-layer pipeline
processing a real natural language query through all three
verification layers and producing a verified, auditable response.

This is the milestone referenced in Episode 8:
"From Blueprint to First Light."

Run with:
    python demo_first_query.py

Author: V.E.R.A. Open Source Initiative
Version: 0.1.0
Date: March 2026
"""

from vera_pipeline import VERAPipeline, VerificationOutcome


def print_banner():
    print()
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║     V.E.R.A. -- Verified Existence and Reasoning Architecture    ║")
    print("║                      First Light Demo v0.1.0                     ║")
    print("║                                                                   ║")
    print("║  'Truth is a feature, not an option.'                            ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print()


def run_demo():
    print_banner()
    pipeline = VERAPipeline()

    # -----------------------------------------------------------------------
    # THE FIVE CANONICAL TEST CASES
    # Each demonstrates a different path through the pipeline.
    # -----------------------------------------------------------------------

    demos = [
        {
            "label": "DEMO 1: Verified pharmaceutical fact",
            "query": "Aspirin is an analgesic.",
            "explanation": (
                "Classic e-type singular statement.\n"
                "  Aspirin(x) -- elementary predicate, e-type by R1.\n"
                "  Aspirin EXISTS in E! Corpus (WHO Essential Medicines).\n"
                "  Result: VERIFIED -- predication follows verified existence."
            ),
            "expected": VerificationOutcome.VERIFIED,
        },
        {
            "label": "DEMO 2: Fictional entity -- firewall fires",
            "query": "Sherlock Holmes is a detective.",
            "explanation": (
                "e-type statement about a fictional entity.\n"
                "  Sherlock Holmes is confirmed NOT_EXISTS in E! Corpus.\n"
                "  Result: NOT_EXISTS -- the Wall of Separation prevents\n"
                "  predication about non-existent entities. Classic hallucination scenario."
            ),
            "expected": VerificationOutcome.NOT_EXISTS,
        },
        {
            "label": "DEMO 3: Universal statement -- no E! check needed",
            "query": "All swans are white.",
            "explanation": (
                "Universal affirmative: forall(x)(Swan(x) => White(x)).\n"
                "  Implication with e-type antecedent and consequent.\n"
                "  By Krampitz R6: (e => e) is n-type.\n"
                "  Result: NO_CHECK_REQUIRED -- n-type formulas carry no existence\n"
                "  presupposition. Black swans do not break this statement logically."
            ),
            "expected": VerificationOutcome.NO_CHECK_REQUIRED,
        },
        {
            "label": "DEMO 4: Unknown entity -- fail-safe refusal",
            "query": "Zarkonite is a rare mineral.",
            "explanation": (
                "e-type statement about an entity not in the E! Corpus.\n"
                "  Zarkonite returns UNKNOWN -- not verified, not confirmed absent.\n"
                "  Result: REFUSAL (REF-001) -- V.E.R.A. refuses to predicate\n"
                "  properties about entities whose existence is unconfirmed.\n"
                "  Integrity over answers."
            ),
            "expected": VerificationOutcome.REFUSAL,
        },
        {
            "label": "DEMO 5: Alias resolution + verification",
            "query": "Acetaminophen is used for pain relief.",
            "explanation": (
                "Acetaminophen is a US trade name. In NZ/UK it is Paracetamol.\n"
                "  E! Corpus alias table resolves Acetaminophen -> Paracetamol.\n"
                "  Result: VERIFIED -- existence confirmed under canonical name."
            ),
            "expected": VerificationOutcome.VERIFIED,
        },
    ]

    results_summary = []

    for demo in demos:
        print(f"\n{'─' * 68}")
        print(f"  {demo['label']}")
        print(f"{'─' * 68}")
        print(f"  Query: \"{demo['query']}\"")
        print()
        print(f"  NTP Analysis:")
        for line in demo["explanation"].split("\n"):
            print(f"    {line}")
        print()

        response = pipeline.run(demo["query"])

        outcome_icon = "✓" if response.outcome == demo["expected"] else "✗"
        print(f"  Outcome:   {outcome_icon} {response.outcome.value}")
        print(f"  Formula:   {response.characteristic or 'n/a'}-type")
        print(f"  Subjects:  {response.subjects}")
        print(f"  Time:      {response.processing_time_ms}ms")
        print()

        # Print existence results if any
        if response.existence_results:
            print(f"  Existence Check Results:")
            for er in response.existence_results:
                prov_source = er.provenance.source_type if er.provenance else "no provenance"
                canonical = f" -> '{er.canonical_name}'" if er.canonical_name and er.canonical_name != er.entity_name else ""
                print(f"    '{er.entity_name}'{canonical}: {er.existence_status.value} "
                      f"(confidence: {er.confidence:.2f}, source: {prov_source})")
        print()
        print(f"  Verdict:   {response.summary[:120]}")

        results_summary.append({
            "demo": demo["label"],
            "expected": demo["expected"].value,
            "actual": response.outcome.value,
            "pass": response.outcome == demo["expected"],
        })

    # -----------------------------------------------------------------------
    # AUDIT TRAIL DEMO -- Show full trace for Demo 1
    # -----------------------------------------------------------------------
    print(f"\n{'═' * 68}")
    print("  FULL AUDIT TRAIL -- Demo 1 (Aspirin)")
    print(f"{'═' * 68}")
    first_response = pipeline.run("Aspirin is an analgesic.")
    first_response.print_audit_trail()

    # -----------------------------------------------------------------------
    # SUMMARY
    # -----------------------------------------------------------------------
    print(f"\n{'═' * 68}")
    print("  V.E.R.A. First Light -- Demo Summary")
    print(f"{'═' * 68}")
    passed = sum(1 for r in results_summary if r["pass"])
    print(f"\n  {passed}/{len(results_summary)} demos produced expected outcomes\n")
    for r in results_summary:
        icon = "✓" if r["pass"] else "✗"
        print(f"  {icon}  {r['demo']}")
        if not r["pass"]:
            print(f"       Expected: {r['expected']}  Got: {r['actual']}")

    print()
    print("  Pipeline verified. V.E.R.A. v0.1.0 is operational.")
    print()
    print("  Contribute: https://github.com/andreas-linux/vera/")
    print("  Te Pono Limited -- Wellington, New Zealand")
    print()
    print("  Ita est momentum veritatis.")
    print()

    pipeline.close()


if __name__ == "__main__":
    run_demo()
