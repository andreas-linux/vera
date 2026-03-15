# Contributing to V.E.R.A.

Thank you for your interest in V.E.R.A. This is an open-source project building AI verification infrastructure grounded in formal logic. Contributions are welcome from developers, logicians, and domain experts.

---

## Who We Are Looking For

There are three clear entry points. Pick the one that fits your background.

---

### 1. Python Developers

**What we need:**

The core pipeline is working. The next layer of implementation work is well-defined and ready to pick up.

**First task — E! Corpus expansion:**

The seed corpus ships with 9 entities. The Pharma 500 milestone requires 500 common drug entities with aliases, properties, and provenance. The `add_entity()` method in `e_verification_service.py` is the interface. A contributor could:

- Write a script to ingest WHO Essential Medicines list entries into the corpus
- Write a Wikidata query to pull entity data (see `IF-006` in the interface spec)
- Propose a bulk import format and open a PR

**Second task — formula parser extension:**

`formula_parser.py` handles common statement types. It does not yet handle:

- Compound sentences with multiple clauses
- Existence claims ("There is an X", "X exists")
- Comparative statements ("X is more Y than Z")

Pick one pattern, write the tests first (matching the existing test structure), then implement.

**Skills required:** Python 3.10+, basic SQL (SQLite), willingness to read the NTP rules. The rules are documented in the code and in `docs/ntp_rules.md`. You do not need a logic background to implement them — they are algorithmic.

---

### 2. Logicians and NLP Researchers

**What we need:**

The hardest unsolved problem in V.E.R.A. is claim extraction: given a paragraph of free text, identify every atomic assertion and determine which entities each assertion is *about*.

This is the difference between:

> "Aspirin, discovered in 1897, is widely used as an analgesic and anti-inflammatory agent."

...and the three distinct existence-loaded claims buried in that sentence. A standard NLP pipeline will parse the sentence. It will not decompose it into NTP-grounded atomic predicates with correctly identified subjects.

We are explicitly labelling this as **research, not engineering.** We need someone who can think about the problem, not just implement a regex. If you have a background in:

- Computational linguistics or formal semantics
- Information extraction or relation extraction
- Proof theory or type-theoretic approaches to NLP

...this is the problem worth your attention.

**How to engage:** Open an issue titled `[Research] Claim extraction from prose` and describe your approach. We will iterate from there. No PR required at first contact.

---

### 3. Domain Experts and Data Contributors

**What we need:**

The E! Corpus is the evidence layer of V.E.R.A. Its quality determines the quality of verification. We need curated, verified entity databases for specific domains. This is the **lowest barrier to entry and the highest immediate value.**

A domain contribution is a structured list of:

- Canonical entity names
- Aliases (trade names, abbreviations, regional variants, translations)
- Existence status (EXISTS / NOT_EXISTS for confirmed fictional or deprecated entities)
- One or more provenance sources (URL, source type, reliability score)
- Optional: key properties (e.g. drug class, mechanism, CAS number)

**Format:**

Use the `add_entity()` method in `e_verification_service.py`, or submit a JSON file in this structure:

```json
{
  "canonical_name": "Ibuprofen",
  "entity_type": "SUBSTANCE",
  "status": "EXISTS",
  "confidence": 1.0,
  "aliases": [
    ["Advil", "TRADE_NAME"],
    ["Nurofen", "TRADE_NAME"],
    ["Ibuprofenum", "INN"]
  ],
  "provenance": {
    "source_type": "WHO_ESSENTIAL_MEDICINES",
    "source_url": "https://list.essentialmedicines.who.int/",
    "reliability_score": 0.99
  },
  "properties": [
    ["drug_class", "NSAID"],
    ["cas_number", "15687-27-1"]
  ]
}
```

**Target domains for v0.2:**
- Pharmaceuticals (Pharma 500: 500 common drugs, WHO Essential Medicines list)
- New Zealand geographic entities (cities, regions, iwi)
- International organisations (UN bodies, standards organisations)

Submit domain contributions as a PR to `data/corpus/` or open an issue to discuss scope first.

---

## Development Setup

```bash
git clone https://github.com/andreas-linux/vera.git
cd vera
pip install -e ".[dev]"
pytest tests/
```

All PRs should pass the existing test suites before submission. New functionality requires new tests.

---

## Code Standards

- Python 3.10+ with type annotations
- Docstrings on all public classes and methods
- Clear separation of validated NTP rules (sourced from Wessel 1992 / Krampitz 1990) from implementation choices
- No assertion of existence without E! Corpus verification (this is the whole point)
- British English in comments and documentation (the project is based in New Zealand)

---

## NTP Source Materials

The NTP rules implemented in V.E.R.A. are validated against:

> Wessel, H. (1992). *Existenz, Ununterscheidbarkeit, Identität.* Wissenschaftliche Zeitschrift der Humboldt-Universität zu Berlin.

> Krampitz, K.-H. (1990). *Dissertation B.* Humboldt-Universität zu Berlin.

If you have access to Wessel (1989) *Logik* or Wessel (1996) *Logik und Philosophie*, please open an issue. These are primary sources still needed for theoretical validation of remaining NTP elements.

---

## Governance

The architecture lead and NTP domain authority is Andreas Hamberger (M.A. Phil in Logic, Humboldt University Berlin; Wessel's research assistant 1991–1996). Significant deviations from NTP rules require sign-off from the architecture lead. Implementation choices within the defined interfaces are open for community contribution.

---

## Licence

By contributing to V.E.R.A., you agree that your contributions will be licensed under GPL-3.0.

---

*Te Pono Limited | Wellington, New Zealand*
*Ita est momentum veritatis.*
