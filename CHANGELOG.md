# Changelog

All notable changes to V.E.R.A. will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
