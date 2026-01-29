#!/usr/bin/env python3
"""
V.E.R.A. Demo: Hallucination Prevention in Action

This script demonstrates how V.E.R.A. prevents AI hallucination
by verifying entity existence before allowing predication.

Run with: python examples/demo_basic.py
"""

from vera import VERAPipeline, VerificationStatus


def main():
    print()
    print("=" * 60)
    print("  V.E.R.A. - Hallucination Prevention Demo")
    print("=" * 60)
    print()
    
    # Initialize pipeline with test data
    pipeline = VERAPipeline(seed_data=True)
    
    # Test statements
    statements = [
        # Safe: n-type (no existence requirement)
        "All swans are white",
        
        # Safe: subject exists in E! Corpus
        "Socrates is mortal",
        "Albert Einstein is a physicist",
        "The Higgs boson is an elementary particle",
        
        # BLOCKED: subject confirmed not to exist
        "Unicorns have magical powers",
        "Sherlock Holmes lives in London",
        "Zeus controls the weather",
        
        # BLOCKED: subject unknown (would hallucinate!)
        "Professor Smith published a paper",
        "The XYZ Corporation announced earnings",
    ]
    
    print("Testing statements through V.E.R.A. pipeline...\n")
    
    for statement in statements:
        result = pipeline.verify(statement)
        
        # Color-coded status (using Unicode for terminal)
        if result.verification_status == VerificationStatus.VERIFIED:
            status_icon = "✅"
            action = "ALLOWED"
        elif result.verification_status == VerificationStatus.SKIPPED:
            status_icon = "⏭️ "
            action = "SAFE (n-type)"
        elif result.verification_status == VerificationStatus.REFUSED:
            status_icon = "🚫"
            action = "BLOCKED"
        elif result.verification_status == VerificationStatus.UNCERTAIN:
            status_icon = "⚠️ "
            action = "BLOCKED (would hallucinate)"
        else:
            status_icon = "❓"
            action = result.verification_status.value
        
        print(f"{status_icon} \"{statement}\"")
        print(f"   Status: {result.verification_status.value}")
        print(f"   Action: {action}")
        
        if result.subject_verifications:
            for sv in result.subject_verifications:
                print(f"   E!({sv.subject_name}) = {sv.existence_status.value}")
        print()
    
    # Summary
    print("=" * 60)
    print("Summary:")
    print("  - n-type formulas (universals): Safe without E! check")
    print("  - e-type with EXISTS: Predication allowed")
    print("  - e-type with NOT_EXISTS: Predication blocked (fictional)")
    print("  - e-type with UNKNOWN: Predication blocked (hallucination)")
    print("=" * 60)
    
    pipeline.close()


if __name__ == "__main__":
    main()
