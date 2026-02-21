# ADR-0008: Progressive Understanding Pipeline

- **Status**: Implemented (v8 experiment)
- **Date**: 2026-02-20
- **Updated**: 2026-02-21
- **Deciders**: Wayne
- **Supersedes**: ADR-0001 (Multi-Agent Pipeline Architecture) — evolves the extraction approach

## Context

Our extraction experiments (v6 whole-doc, v7 two-pass) revealed a fundamental mismatch: we use a short, generic prompt to process long, structured documents in one shot. The results show:

1. **Entity extraction is good** (87.5% core recall) — the model can identify *what* a document talks about
2. **Relationship extraction is the bottleneck** (~20-27% recall) — the model struggles to capture *how* concepts relate, especially across distant parts of the text
3. **Systematic errors persist**: PartOf/HasProperty misuse, direction reversal, redundant entities — these are symptoms of the model lacking global context when making local decisions
4. **Stronger models don't solve this**: v7 used Gemini 2.5 Flash for relations (6x pricier than Lite) with no clear improvement, suggesting the problem is architectural, not model-capability

The root cause: asking an LLM to simultaneously understand document structure, identify entities, determine relationship types, and get directionality right — all from a single prompt — is too many degrees of freedom. Humans don't read this way. We skim first, build a mental model, then fill in details progressively.

## Decision

Replace one-shot extraction with a multi-phase **Progressive Understanding** pipeline that mirrors how humans read and comprehend structured documents.

### Key Design Principles

1. **Open edge types**: Relationship types are NOT hardcoded. The model creates descriptive types that accurately describe the connection (IsA, Causes, Requires, Illustrates, Implements, Uses, etc.). Hardcoding a fixed list is inelegant and limits expressiveness. Edge types are essentially descriptions of relationships — as long as they make sense, any type is valid.

2. **Programmatic chunking**: Chunking is done deterministically by detecting section headers, numbered sections, and paragraph boundaries — no LLM involvement. The narrative from Phase 0 provides sufficient context for each chunk. AI-driven chunking adds complexity without proportional value.

3. **Lite-only**: Each phase has a narrow, well-defined task. Flash Lite suffices for all phases.

### Phase 0: Skim

Read the document to produce a document schema and narrative root.

**Input**: Full document text (for docs < 20K tokens) or opening + section hints (for larger docs)
**Output**: Document Schema + Narrative Root

```json
{
  "topic": "Condition Variables in OS Threading",
  "content_type": "textbook_chapter",
  "theme": "Replacing inefficient busy-waiting with a sleep/wake mechanism...",
  "narrative_root": {
    "summary": "2-4 sentence overview of what the document teaches and how",
    "key_tension": "the central tradeoff or problem being navigated",
    "learning_arc": "motivation → mechanism → application → rules"
  },
  "expected_core_entities": [
    {"label": "Condition Variable", "type": "Concept", "why": "Central topic"}
  ],
  "document_structure": [
    {"section": "Introduction & Motivation", "purpose": "Why CVs exist"}
  ]
}
```

**Key design choices**:

1. **Narrative root starts here**. The `theme`, `key_tension`, and `learning_arc` fields frame the entire document comprehension. This is passed to every subsequent chunk as context.

2. **No chunking plan**. Chunking is handled programmatically by `src/chunking/programmatic_chunker.py` which splits at section headers or paragraph boundaries.

3. **Expected core entities are hypotheses**, not ground truth. Phase 1 may discover entities not predicted here, and that's fine. But having these priors helps the model in Phase 1 avoid creating redundant variants.

### Programmatic Chunking

Between Phase 0 and Phase 1, the document is chunked programmatically:

1. **Detect section headers**: markdown `#`, numbered sections (`30.1 ...`), ALL-CAPS lines, bold markdown headers
2. **Split at headers** if ≥ 3 headers found, otherwise split at paragraph boundaries
3. **Post-process**: merge chunks < 200 tokens, split chunks > 3000 tokens

This is deterministic, fast, and produces consistent results. The narrative context from Phase 0 compensates for the lack of semantic chunk boundaries.

### Phase 1: Sequential Chunk Processing (with Accumulating Context)

Process chunks in document order. Each chunk receives:
- The **document schema** from Phase 0
- The **running narrative** (accumulated summary of everything processed so far)
- The **entity registry** (all entities discovered so far)

**Input per chunk**: chunk text + document schema + running narrative + entity registry
**Output per chunk**:

```json
{
  "new_entities": [...],
  "relationships": [...],
  "narrative_update": "2-3 sentences continuing the story..."
}
```

**Relationship validation**: Only checks entity IDs exist and no self-loops. Types are open — the model chooses whatever type best describes the relationship.

### Phase 2: Consolidation

Review and fix the complete graph.

**Tasks**:
- Deduplicate entities (merge variants)
- Add missing cross-section relationships
- Correct relationship types/directions
- Produce final narrative summary

### Narrative Tree Structure

The accumulating narrative is stored as a **tree**, not a flat string, because documents branch:

```
root: "Chapter on Condition Variables"
├── motivation: "CVs replace inefficient spin-waiting..."
├── api_and_usage: "wait() and signal() are CV's two operations..."
│   └── join_example: "Parent-child join demonstrates basic CV pattern..."
├── producer_consumer: "P/C is the canonical CV application..."
│   ├── single_cv_problem: "Using one CV causes deadlock"
│   └── two_cv_solution: "Separate empty/fill CVs..."
└── semantics: "Mesa vs Hoare semantics..."
```

(Currently implemented as flat accumulating string; tree structure for future iteration.)

## Alternatives Considered

### Alternative 1: Better Prompts on One-Shot Extraction
- **Why not**: v6→v7 showed that even switching to a stronger model with better prompts didn't meaningfully improve edge quality; the problem is structural

### Alternative 2: AI-Driven Chunking (Phase 0 produces chunking plan)
- **Tried in v8 initial implementation**: Phase 0 generated text markers for chunk boundaries
- **Problems**: 48.5% coverage, markers hard to find in document, added complexity to Phase 0 prompt, required complex validation logic
- **Why removed**: Programmatic chunking with narrative context achieves the same goal more reliably

### Alternative 3: Hardcoded Edge Types
- **Tried in v8 initial implementation**: 10 fixed types (IsA, PartOf, Causes, etc.), dropped any relationship using a different type
- **Problems**: 33% of relationships dropped as "illegal type" — the model naturally creates descriptive types like Uses, Requires, Illustrates
- **Why removed**: Edge types are just descriptions of relationships. Any meaningful type is valid. Hardcoding is inelegant and wasteful.

## Consequences

### Positive
- **Better edge quality**: Each chunk processed with full context of what came before
- **Open types**: Model freely expresses the nature of relationships without artificial constraints
- **Deterministic chunking**: No LLM variability in chunk boundaries
- **Dual-use narrative**: The accumulating summary is both an engineering artifact AND a user-facing learning aid
- **Lite-friendly**: Each phase has a narrow, well-defined task
- **Debuggable**: Each phase produces inspectable intermediate outputs

### Negative
- **More LLM calls**: N chunks → N+2 calls minimum
- **Sequential dependency**: Chunks must be processed in order
- **Narrative quality depends on early chunks**: If Phase 0 misreads the document, errors propagate

### Risks
- **Narrative drift**: Accumulating context might grow too large → mitigate with compression and eventually tree structure
- **Phase 0 failure**: If introduction is atypical → mitigate by passing full doc for small docs, or allow fallback
- **Evaluation challenge**: Open edge types mean the evaluator needs semantic matching, not exact string matching

## Implementation

- `src/extraction/progressive_prompts.py` — Three prompts (skim, chunk extract, consolidation)
- `src/extraction/progressive_extractor.py` — Full pipeline orchestrator
- `src/chunking/programmatic_chunker.py` — Deterministic section/paragraph-based chunker
- `src/validation/phase0_validator.py` — Schema validation (chunking validation preserved for reference)
- `experiments/runners/run_progressive.py` — Experiment runner with detailed reporting
- `experiments/configs/v8_progressive.yaml` — Experiment configuration

## Related

- ADR-0006: Tiered Model Strategy — Progressive Understanding makes Lite sufficient for all phases
- ADR-0003: CocoIndex-Style Structured Extraction — Phase 1 still uses structured JSON output
- experiments/results/v6-whole-doc/ — baseline one-shot results
- experiments/results/v7-two-pass/ — two-pass results showing model upgrade alone is insufficient
