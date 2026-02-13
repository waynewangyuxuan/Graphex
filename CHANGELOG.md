# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Project structure with Meta folder hierarchy
- Core documentation (Product.md, Technical.md)
- Research documents (Cognitive_Foundations.md, Node_Edge_Schema.md)
- Milestone tracking system
- ADR system for architectural decisions
- CI/CD pipeline for Python
- **Benchmark system** for evaluating extraction quality (2026-02-12)
  - Ground Truth templates (`benchmark/templates/`)
  - Ground Truth for 3 test documents (threads-cv, MiroThinker, threads-bugs)
  - Pipeline diagnosis report (`benchmark/PIPELINE_DIAGNOSIS.md`)
- **Prompt Engineering tracking** (`Meta/Research/Prompt_Engineering_Log.md`) (2026-02-12)

### Changed
- **MVP Node types**: 5 → 6 types (added `Method` for functions/operations) (2026-02-12)
- **MVP Edge types**: 8 → 10 types (added `Enables`, `Prevents`, `Contrasts`) (2026-02-12)
- Clarified `Agent` type to exclude copyright/reference authors (2026-02-12)
- Added `RelatedTo` usage guideline: should be <40% of total edges (2026-02-12)

### Deprecated
-

### Removed
-

### Fixed
-

### Security
-

---

<!--
Template for new versions:

## [X.Y.Z] - YYYY-MM-DD

### Added
- New features

### Changed
- Changes in existing functionality

### Deprecated
- Soon-to-be removed features

### Removed
- Removed features

### Fixed
- Bug fixes

### Security
- Security fixes
-->
