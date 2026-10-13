# Changelog

All notable changes to V.E.R.A. will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- `import vera` failed on any installed copy: three modules used bare imports that only resolved from inside `src/vera`. They are relative now.
- The shipped test file could not be collected (the package did not export `Predicate` and the other formula classes it imports).
- `pip install` put a `vera` command on the path pointing at a `vera.cli` module that did not exist.
- 137 logic symbols in the Krampitz analyser and the parser were double-encoded (`âˆ§` for `∧` and so on).
- `examples/demo_basic.py` imported names that never existed (`VerificationStatus`, `pipeline.verify`).
- The Zeus test entity carried the alias "Jupiter", which would have made the planet NOT_EXISTS.

### Changed
- **One E! Corpus.** `e_corpus.py` and `e_verification_service.py` were two implementations with different schemas. They are merged into `e_verification_service.py` on a single schema in `corpus_schema.py`, applied by numbered migrations (`PRAGMA user_version`). v0.1 corpus files are upgraded in place; a file from a newer version is refused. `e_corpus.py` is removed and its 19 checks are ported to `tests/test_corpus.py`.
- Provenance records whether a source is **resolvable** (carries a URL) or **named** (identified by name only), and may carry a `back_reference` (where the source was found, never evidence). Both rules are enforced by the database as well as by `add_entity`.
- `EVerificationService` and `VERAPipeline` take `seed=False` for a corpus of your own.
- Version is single-sourced from `vera.__version__` (now `0.2.0.dev0`). Author contact is andreas@thehambergerreport.com.

### Added
- `vera` command line: `check`, `identity`, `corpus init | stats | lookup | search | add`.
- `resolve_identity`, `search_entities`, `add_property` and `add_identity_relation` on the unified service.
- CI on Python 3.10 to 3.13, including an install-and-import check from outside the source tree, and a build check.
- The suites embedded in `krampitz_analyzer` and `e_verification_service`, and both demos, now run under pytest.

### Planned (carried forward)

### Planned
- Wikidata ETL pipeline for E! Corpus population
- FastAPI REST server (IF-002, IF-003 endpoints)
- Claude API integration with NTP constraints
- D-Service full implementation (D1-D4 relations)

## [0.1.0] - 2026-01-30

### Added
- **Layer 1: Krampitz Load Analyzer**
  - Implemented R1-R9 existential loading rules from Wessel (1992)
  - Formula AST: Predicate, Negation, Conjunction, Disjunction, Implication, Biconditional, Universal, Existential
  - Inner negation support for precise NTP semantics
  - Complete test suite (12/12 passing)

- **Formula Parser**
  - Natural language to NTP formula conversion
  - Pattern-based parsing for common statement types
  - Support for: universal, particular, singular, conditional, existence claims
  - Recursive parsing for compound statements
  - Test suite (15/15 passing)

- **Layer 2: E! Verification Service**
  - SQLite-based E! Corpus schema (PostgreSQL compatible)
  - Entity, Alias, Provenance, Property, IdentityRelation tables
  - exists() API with fuzzy matching and alias support
  - resolve_identity() implementing D1-D4 relations
  - Test data seeding with philosophical examples
  - Test suite (19/19 passing)

- **Integrated Pipeline**
  - VERAPipeline combining all components
  - Complete verification flow: Parse → Analyze → Verify → Result
  - Human-readable reasoning chains
  - Verification statuses: VERIFIED, REFUSED, UNCERTAIN, VACUOUS, SKIPPED
  - Integration test suite (11/12 passing)

- **Documentation**
  - TOGAF ADM architecture documents (Phase A, B, C/D)
  - NTP formal specification with validated rules
  - Hexadecagon diagram documentation
  - README with usage examples

### Technical Notes
- Pure Python implementation (no external dependencies for core)
- In-memory SQLite for testing, file-based for persistence
- Designed for Claude API integration (planned)

## [0.0.1] - 2026-01-28

### Added
- Initial project structure
- TOGAF Phase A Architecture Vision document
- NTP rule extraction from Wessel (1992)
- Project handover documentation

---

## Version History Summary

| Version | Date | Highlights |
|---------|------|------------|
| 0.1.0 | 2026-01-30 | Full prototype: Krampitz Analyzer, E! Corpus, Pipeline |
| 0.0.1 | 2026-01-28 | Project inception, architecture documents |

[Unreleased]: https://github.com/vera-project/vera/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/vera-project/vera/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/vera-project/vera/releases/tag/v0.0.1
