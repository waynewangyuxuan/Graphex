# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Two-Pass Extraction (v7)** (2026-02-20)
  - `src/extraction/two_pass_extractor.py`: Pass 1 entities (Flash Lite) → Pass 2 relations (Flash)
  - `experiments/runners/run_two_pass.py`: Two-pass experiment runner
  - `experiments/configs/v7_two_pass.yaml`: Experiment config for ADR-0006 tiered model strategy
  - New prompts: `ENTITY_ONLY_PROMPT` (entity-only extraction), `RELATION_PROMPT_TEMPLATE` (relation extraction with direction guidance)
  - Result: 87.5% core node recall (same as v6), 37.5% core edge recall (same as v6), but 2x token cost — stronger model did not improve edge quality
- **Config-Driven Experiment Organization** (2026-02-20)
  - `experiments/configs/`: YAML configs for all experiments (v1-v6), versioned and committed
  - `experiments/runners/`: Config-driven extraction and evaluation runners
  - `src/extraction/`: Promoted from spike — structured_extractor.py, prompts.py, merger.py
  - `src/evaluation/`: Promoted from spike — evaluator.py
  - Multi-prompt support: PROMPTS registry with "chunk" and "whole_doc" variants
  - ADR-0007: Experiment organization and dead code cleanup
- **Whole-Document Extraction (v6)** (2026-02-20)
  - Single LLM call for entire document — no chunking, no ER needed
  - `WHOLE_DOC_PROMPT`: thorough extraction prompt for long-context models
  - Result: 20 entities, 87.5% core node recall, 1 LLM call, ~11k input tokens
- **Graphiti-Style Cascading Entity Resolution** (2026-02-20)
  - `src/resolution/entity_resolver.py`: Three-layer cascade (exact match → entropy-gated Jaccard → LLM batch dedup)
  - `src/resolution/parallel_merge.py`: O(log N) binary reduction merge with ThreadPoolExecutor
  - ADR-0005: Replaces embedding approach; entropy gate prevents over-merging of short entity names
- **CocoIndex-style Structured Extraction Spike** (2026-02-19)
  - `benchmark/scripts/cocoindex_spike.py`: Single-call LLM extraction (entities + relationships)
  - Evaluated against threads-cv Ground Truth: 100% core node recall, 50% core edge recall
  - ADR-0003: Decision to adopt structured extraction pattern over multi-agent pipeline
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
- **Knowledge Graph Health Metrics** (2026-02-14)
  - `Meta/Research/Knowledge_Graph_Health_Metrics.md`: Cognitive science-based guidelines
  - `Meta/Research/Graph_Density_Analysis.md`: Token-to-node and edge-to-node ratios
  - Quality benchmarks for different content types (textbook, paper, technical doc, news)

### Changed
- **Chunk size**: 512 chars (~128 tokens) → 6000 chars (~1500 tokens) (2026-02-20)
  - Fixed `length_function=len` misunderstanding (was counting chars, not tokens)
  - Result: 18 entities (was 67), 87.5% core node recall (was 50%), 75% less token usage
- **Entity Resolution strategy**: Embedding cosine similarity → Graphiti-style cascading (2026-02-20)
  - ADR-0004 (embedding, superseded) → ADR-0005 (Graphiti cascading, accepted)
  - Root cause: embedding cosine unreliable for short entity names ("Lock", "Mutex", "Thread")
- **MVP Node types**: 5 → 6 types (added `Method` for functions/operations) (2026-02-12)
- **MVP Edge types**: 8 → 11 → 10 types (added `Enables`, `Prevents`, `Contrasts`; removed `RelatedTo`) (2026-02-12)
- Clarified `Agent` type to exclude copyright/reference authors (2026-02-12)
- **Edge extraction strategy**: If no specific type fits, DON'T create the edge (2026-02-12)

### Deprecated
-

### Removed
- **Dead code cleanup** (2026-02-20): `src/agents/`, `src/pipeline/`, `src/context/`, `examples/`
  All superseded by CocoIndex-style structured extraction (ADR-0003). -3,435 lines.
- **`RelatedTo` edge type** (2026-02-12): Too generic - nodes with edges are obviously related.
  This "fallback" option led to lazy classification (76% usage in benchmark tests).
  New strategy: quality over quantity, only create edges that can be precisely typed.

### Fixed
- **0 edges bug in EnhancedPipeline** (2026-02-14): Edges were being rejected because
  nodes weren't added to the graph until after Phase 3, but `add_edge()` validates
  that source/target nodes exist. Fix: add nodes to graph immediately after extraction
  (before relation extraction), not after grounding verification.

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
