# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Marker PDF Parser Integration** (2026-02-24) — Optional upgrade path for GPU environments
  - `src/parsing/marker_parser.py`: MarkerParser class with lazy model loading, `force_ocr` and `use_llm` options
  - `src/parsing/pdf_parser.py`: Added `create_parser(backend)` factory — auto/pymupdf/marker
  - `experiments/eval/run_eval.py`: Added `--parser auto|pymupdf|marker` CLI flag
  - Currently shelved: too slow on CPU without GPU; `_preprocess_pdf_text` solves core issue

### Fixed
- **Adam paper extraction failure** (2026-02-24) — Was: 9 segments (chunk 1 → 0 segs). Now: 24 segments
  - Root cause: 235 chars of PDF artifacts (U+FFFD) caused LLM JSON output corruption
  - `_preprocess_pdf_text()` removes artifacts at pipeline entry → chunk 1 now produces segments normally
- **PDF Text Pre-processing** (2026-02-23)
  - `_preprocess_pdf_text()`: Cleans U+FFFD replacement chars, normalizes ligatures (ﬁ→fi), strips control chars
  - Applied at pipeline entry before chunking — fixes math-heavy papers (e.g., Adam) where PDF artifacts caused JSON failures
- **Chunk Extraction Salvage & Retry** (2026-02-23)
  - `_salvage_segments()`: Recovers segments from malformed/truncated JSON output (bracket matching + regex fallback)
  - Auto-retry: chunks producing 0 segments get one retry, with salvage attempted on both attempts
  - Diagnostic logging: raw output preview + saved to per_chunk results for post-hoc analysis
- **Phase 1 Evaluation Suite** (2026-02-23)
  - `experiments/eval/test_corpus.py`: 10 CS papers + 5 cross-discipline + 3 multi-doc groups
  - `experiments/eval/scoring_rubric.py`: 7-dimension weighted scoring (narrative_coverage, segment_quality, etc.)
  - `experiments/eval/run_eval.py`: Batch runner with download, per-doc, per-phase execution
  - `src/extraction/multi_doc_extractor.py`: Cross-document relation extraction (builds_on, contradicts, shares_mechanism)
- **Visualization Demos** (2026-02-22)
  - `experiments/results/v9-narrative/graph_demo.html`: D3 force-directed graph (rejected by user)
  - `experiments/results/v9-narrative/tree_demo.html`: Collapsible outline tree (rejected by user)
  - `experiments/results/v9-narrative/mindmap_demo.html`: D3 horizontal mind-map tree (approved)

### Changed
- **Adaptive Chunking** (2026-02-23): Fixed-size chunks → logarithmic scaling
  - `programmatic_chunker.py`: chunk count = log2(doc_tokens / 5000) + 1, with overlap compensation
  - 5K→1 chunk, 10K→2, 15K→3, 20K→3, 50K→4 (sublinear growth)
  - Extraction prompt: "aim for 5-8 segments per section" guidance added
- **Tree Structuring Robustness** (2026-02-23)
  - Dynamic `max_tokens` scaling (segments × 50 + 500, up to 16384) with retry on truncation
  - Cycle detection and breaking in branch parent-child relationships
  - `_building` recursion guard in `build_node()` as safety net

### Fixed
- **Tree structuring silent failure on large documents** (2026-02-23): `max_tokens=4096` caused JSON truncation for docs with 60+ segments. Now scales dynamically.
- **RecursionError in `_assemble_tree`** (2026-02-23): LLM-generated circular parent-child branches (e.g., s3→s5→s3) caused infinite recursion. Now detected and broken.
- **Over-segmentation** (2026-02-23): 2048-token chunks produced 100+ segments for 15-page papers. Adaptive chunking + prompt guidance reduced to 20-65 range.

- **Graph-to-Tree Structuring** (2026-02-21)
  - `src/transform/graph_to_tree.py`: LLM-based narrative graph → reading tree conversion (spine/branch/act/see-also)
  - `NARRATIVE_TREE_PROMPT`: Prompt for spine identification, act grouping, and parent assignment
  - `run_narrative.py`: `--skip-tree` flag and tree visualization in runner output
- **Narrative Review Pass + Anchor Resolution** (2026-02-21)
  - `src/extraction/narrative_extractor.py`: LLM-based review pass (segment dedup, relation fixes, concept normalization)
  - `src/binding/anchor_resolver.py`: Text-graph binding via 5-tier anchor matching (exact → fuzzy → prefix)
  - `NARRATIVE_REVIEW_PROMPT`: Review prompt for post-extraction cleanup
  - Updated chunk extraction prompt with dedup guidance, anchor phrases, and non-teaching content filtering
  - `run_narrative.py`: `--skip-review` flag, review + anchor reporting
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
