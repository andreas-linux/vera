# V.E.R.A. Krampitz Load Analyzer

**Layer 1 of the Triple-Layer Verification System**

## Overview

The Krampitz Load Analyzer implements the validated Krampitz Rules (R1-R9) from Wessel (1992) to determine the existential loading characteristic of NTP formulas.

Every formula is classified as either:
- **e (existentially loaded)** — Presupposes the existence of its subjects to be true
- **n (not existentially loaded)** — No existence presupposition

## Validated Rules

| Rule | Statement |
|------|-----------|
| R1 | All elementary predicative statements are existentially loaded (e) |
| R2 | If A is e, then ~A is n |
| R3 | If A is n, then ~A is e |
| R4 | A ∨ B is e ⟺ (A is e AND B is e) |
| R5 | A ∧ B is e ⟺ (A is e OR B is e) |
| R6 | A ⊃ B is e ⟺ (A is n AND B is e) |
| R7 | A ≡ B is n ⟺ (both A and B are e) OR (both A and B are n) |
| R8 | ∀iA and ∃iA are e ⟺ A is e |
| R9 | A definition A =Def B must be constructed such that A ≡ B is n |

**Source:** Wessel, H. (1992). 'Existenz, Ununterscheidbarkeit, Identität.' K.-H. Krampitz Dissertation B (1990)

## Usage

```python
from krampitz_analyzer import (
    KrampitzAnalyzer, 
    Predicate, 
    Negation, 
    Conjunction,
    Disjunction,
    Implication,
    Universal
)

analyzer = KrampitzAnalyzer()

# Example: "All swans are white" → ∀x(Swan(x) ⊃ White(x))
formula = Universal(
    "x",
    Implication(
        Predicate("Swan", ["x"]),
        Predicate("White", ["x"])
    )
)

result = analyzer.analyze(formula)

print(f"Characteristic: {result.characteristic.value}")  # → n
print(f"Requires E! check: {result.requires_existence_check}")  # → False
print(f"Rule chain: {result.rule_chain}")  # → ['R1', 'R1', 'R6', 'R8']
```

## Why This Matters

The key insight: **"All swans are white"** has characteristic **n** (not existentially loaded).

This means:
1. The statement doesn't presuppose swans exist
2. It's vacuously true if no swans exist
3. V.E.R.A. won't hallucinate swans just because properties are predicated

This is how V.E.R.A. cuts off the hallucination loop at its root.

## Test Results

```
Results: 12 passed, 0 failed out of 12 tests
```

All test cases from VERA_Test_Strategy_v1.0 pass.

## Next Steps

1. **Formula Parser** — Convert natural language to NTP formula AST
2. **E! Corpus Integration** — Layer 2 verification service
3. **API Wrapper** — REST endpoint matching IF-003 specification

## Architecture Integration

This module implements:
- **Interface IF-003** from VERA_Interface_Specifications_v1.0
- **Service SVC-004** (Krampitz Analysis Service) from VERA_Business_Service_Catalog_v1.0
- **Requirements NTP-001 through NTP-009** from VERA_Business_Requirements_Catalogue_v1.0

---

*V.E.R.A. Open Source Initiative | January 2026*

## Licence

This project is licensed under the GNU General Public License v3.0 — see [LICENSE](LICENSE) for details.

Copyright (C) 2026 V.E.R.A. Open Source Initiative
