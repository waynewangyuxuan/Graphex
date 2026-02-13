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
- **Three-Phase Enhanced Pipeline** (2026-02-12)
  - `FirstPassAgent`: Document understanding (identifies teachable concepts)
  - `GroundingVerifier`: Filters entities without proper grounding
  - `EnhancedPipeline`: Orchestrates the three-phase approach
  - Solves the "filename extraction" problem by distinguishing "mentioned" vs "taught"

### Changed
- **MVP Node types**: 5 → 6 types (added `Method` for functions/operations) (2026-02-12)
- **MVP Edge types**: 8 → 11 → 10 types (added `Enables`, `Prevents`, `Contrasts`; removed `RelatedTo`) (2026-02-12)
- Clarified `Agent` type to exclude copyright/reference authors (2026-02-12)
- **Edge extraction strategy**: If no specific type fits, DON'T create the edge (2026-02-12)

### Deprecated
-

### Removed
- **`RelatedTo` edge type** (2026-02-12): Too generic - nodes with edges are obviously related.
  This "fallback" option led to lazy classification (76% usage in benchmark tests).
  New strategy: quality over quantity, only create edges that can be precisely typed.

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
