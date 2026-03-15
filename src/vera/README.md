# V.E.R.A. — Verified Existence and Reasoning Architecture

**Truth is a feature, not an option.**

V.E.R.A. is an open-source AI verification system that eliminates hallucinations by formally separating what things *are* from whether they *exist*. It wraps existing large language models with a triple-layer verification pipeline grounded in Non-Traditional Predication Theory (NTP), developed by Professor Horst Wessel at Humboldt University Berlin.

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

---

## The Core Insight

Standard AI systems confuse two distinct operations:

- **Predication (ℳ)** — describing properties of a thing ("X is an analgesic")
- **Existence (E!)** — asserting that the thing is real ("X exists")

When a model predicts "Aspirin is an analgesic," it is generating a plausible predication. It is not verifying that Aspirin exists. V.E.R.A. keeps these operations strictly separate. No predication is asserted until existence is verified.

This is the logical root of hallucination. V.E.R.A. cuts it there.

---

## How It Works

Every query passes through three layers:

```
Natural Language Query
        │
        ▼
┌─────────────────────────────┐
│  Layer 1: Krampitz Analyzer │  Does this formula presuppose existence?
│  (Krampitz Rules R1–R9)     │  → e-type (yes) or n-type (no)
└─────────────────────────────┘
        │ e-type only
        ▼
┌─────────────────────────────┐
│  Layer 2: E! Verification   │  Does this entity actually exist?
│  (E! Corpus + Provenance)   │  → EXISTS / NOT_EXISTS / UNKNOWN
└─────────────────────────────┘
        │ EXISTS only
        ▼
┌─────────────────────────────┐
│  Layer 3: D-Service         │  Is this the same entity across contexts?
│  (Identity Resolution)      │  → D1–D4 indiscernibility relations
└─────────────────────────────┘
        │
        ▼
Verified Response + Audit Trail
```

**n-type formulas** (e.g. "All swans are white") carry no existence presupposition and pass through without an E! check. **e-type formulas** (e.g. "Aspirin is an analgesic") require verified existence before any predication is asserted. If existence is unverifiable, V.E.R.A. refuses rather than guesses.

---

## Quick Start

```bash
git clone https://github.com/andreas-linux/vera.git
cd vera
pip install -e .
python src/demo_first_query.py
```

Expected output:

```
DEMO 1: Verified pharmaceutical fact
  Query: "Aspirin is an analgesic."
  Outcome: ✓ VERIFIED

DEMO 2: Fictional entity -- firewall fires
  Query: "Sherlock Holmes is a detective."
  Outcome: ✓ NOT_EXISTS

DEMO 3: Universal statement -- no E! check needed
  Query: "All swans are white."
  Outcome: ✓ NO_CHECK_REQUIRED

DEMO 4: Unknown entity -- fail-safe refusal
  Query: "Zarkonite is a rare mineral."
  Outcome: ✓ REFUSAL

DEMO 5: Alias resolution + verification
  Query: "Acetaminophen is used for pain relief."
  Outcome: ✓ VERIFIED  (resolved: Paracetamol, WHO Essential Medicines)

5/5 demos produced expected outcomes.
Pipeline verified. V.E.R.A. v0.1.0 is operational.
```

---

## Use the Pipeline

```python
from vera.vera_pipeline import VERAPipeline

pipeline = VERAPipeline()
response = pipeline.run("Aspirin is an analgesic.")

print(response.outcome)          # VerificationOutcome.VERIFIED
print(response.characteristic)   # 'e'
print(response.summary)
response.print_audit_trail()     # Full reasoning chain
```

---

## Repository Structure

```
vera/
├── src/
│   ├── krampitz_analyzer.py     # Layer 1: Krampitz Rules R1–R9
│   ├── formula_parser.py        # Natural language → NTP formula AST
│   ├── e_verification_service.py # Layer 2: E! Corpus (SQLite)
│   ├── vera_pipeline.py         # Triple-layer pipeline integration
│   └── demo_first_query.py      # End-to-end demo (five canonical cases)
├── tests/
│   └── (pytest suites)
├── docs/
│   └── ntp_rules.md             # NTP formal specification reference
├── CONTRIBUTING.md
├── LICENSE                      # GPL-3.0
└── README.md
```

---

## Test Results (v0.1.0)

| Module | Tests | Status |
|--------|-------|--------|
| Krampitz Analyzer | 12/12 | ✅ All passing |
| Formula Parser | 15/15 | ✅ All passing |
| E! Verification Service | 10/10 | ✅ All passing |
| End-to-end pipeline | 5/5 | ✅ All passing |

Run all tests:
```bash
pytest tests/
```

---

## v0.1.0 Scope

This release contains:

- ✅ Krampitz Load Analyzer (R1–R9, validated from Wessel 1992)
- ✅ Formula Parser (natural language to NTP formula AST)
- ✅ E! Verification Service (SQLite corpus, alias resolution, provenance)
- ✅ Triple-layer pipeline with full audit trail
- ✅ Seed E! Corpus (9 entities, 29 aliases, provenance records)
- ✅ Five-case end-to-end demo

**Not in v0.1.0 (planned):**

- D-Service identity resolution (Layer 3, v0.2 milestone)
- Pharma 500 E! Corpus domain (v0.2 milestone)
- REST API / FastAPI wrapper (v0.2 milestone)
- LLM integration (Claude API wrapping, v0.2 milestone)

---

## The Theory

V.E.R.A. is grounded in Non-Traditional Predication Theory (NTP), developed by Professor Horst Wessel at Humboldt University Berlin. The primary source is:

> Wessel, H. (1992). *Existenz, Ununterscheidbarkeit, Identität.* Wissenschaftliche Zeitschrift der Humboldt-Universität zu Berlin, Reihe Geistes- und Sozialwiss. 41, pp. 30–39.

The Krampitz Rules (R1–R9) derive from:

> Krampitz, K.-H. (1990). *Dissertation B.* Humboldt-Universität zu Berlin.

The architecture lead, Andreas Hamberger, was Wessel's research assistant from 1991 to 1996 and is the primary domain authority on NTP for this project. No external NTP expert is required.

---

## Contributing

We are looking for:

- **Python developers** — extend the E! Corpus, improve the formula parser, implement the D-Service
- **Logicians and NLP researchers** — the claim extraction problem is genuinely hard; we need researchers, not just engineers
- **Domain experts** — contribute a verified E! Corpus domain (pharmaceuticals, geography, organisations)

See [CONTRIBUTING.md](CONTRIBUTING.md) for first tasks and how to get started.

---

## Architecture and Design

The full TOGAF ADM architecture is documented in the V.E.R.A. Saturday LinkedIn series:

| Episode | Title | TOGAF Phase |
|---------|-------|-------------|
| 1 | The Project Charter | Preliminary |
| 2 | The 98 Rules That Make AI Stop Lying | Business Requirements |
| 3 | The Architecture of Truth | Phase A |
| 4 | The Blueprint for Verified Intelligence | Phase B |
| 5 | Where Logic Meets Data | Phase C |
| 6 | The Engine Room | Phase D |
| 7 | The Verification Gap | Phase E |
| 8 | From Blueprint to First Light | Phase F |

[Follow the series on LinkedIn →](https://www.linkedin.com/in/andreashamberger/)

---

## Licence

GPL-3.0. The core V.E.R.A. engine is and will remain open source.

Domain-specific E! Corpora (curated, validated, provenance-tracked entity databases for specific industries) are developed and licensed separately by Te Pono Limited, Wellington, New Zealand.

---

*Te Pono Limited | Wellington, New Zealand*
*Ita est momentum veritatis.*
