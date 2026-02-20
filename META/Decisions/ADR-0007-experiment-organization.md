# ADR-0007: Experiment Organization and Dead Code Cleanup

## Status
Accepted

## Date
2026-02-20

## Context

After three pipeline iterations (multi-agent → enhanced three-phase → CocoIndex-style structured extraction), the codebase accumulated:

- **Dead code**: `src/agents/` (6 files), `src/pipeline/` (3 files), `src/context/` (2 files) — all superseded by ADR-0003 structured extraction
- **Spike-as-production**: `benchmark/scripts/cocoindex_spike.py` grew into a 389-line monolith with extraction, merging, evaluation, and CLI
- **Hardcoded params**: chunk_size, model name, thresholds scattered in .py files
- **examples/ graveyard**: 4 test scripts from previous approaches, never cleaned up
- **No experiment reproducibility**: past experiments undocumented, params lost to git history

## Decision

Adopt config-driven experiment organization pattern (source: KGGen, AI2 Tango, PyKEEN):

1. **Clean `src/`**: Remove all superseded code. `src/` contains only the current approach. Git history preserves old code.

2. **Promote spike logic to `src/`**:
   - `src/extraction/` — structured_extractor.py, prompts.py, merger.py
   - `src/evaluation/` — evaluator.py

3. **Create `experiments/` directory**:
   - `experiments/configs/` — YAML configs defining each experiment (committed, versioned)
   - `experiments/runners/` — Scripts that load config and call `src/` functions
   - `experiments/results/` — `.gitignored` output artifacts, reproducible from config

4. **Retroactive configs**: Create YAML configs for all 5 past experiments (v1-v5) as documentation of what was tried.

## Consequences

### Positive
- `src/` is clean: only active, tested code
- Every experiment is reproducible from its config file
- New experiments require only a new YAML file, not new code
- Clear separation: library (src/) vs orchestration (experiments/) vs ground truth (benchmark/)

### Negative
- One-time migration effort
- Removing `test_entity_registry.py` and one test from `test_edge_fix.py` (tested dead code)

### Files Removed
- `src/agents/` (base.py, entity_extractor.py, relation_extractor.py, validator.py, first_pass_agent.py, grounding_verifier.py)
- `src/pipeline/` (pipeline.py, enhanced_pipeline.py, state.py, __init__.py)
- `src/context/` (context_builder.py, entity_registry.py, __init__.py)
- `examples/` (4 scripts + output/)
- `tests/unit/test_entity_registry.py`

### Files Added
- `src/extraction/` (structured_extractor.py, prompts.py, merger.py)
- `src/evaluation/` (evaluator.py)
- `experiments/configs/` (v1-v5 YAML configs)
- `experiments/runners/` (run_extraction.py, run_evaluation.py)

## Knowledge Source
Prism output/experiment-organization-module (KGGen, AI2 Tango, PyKEEN patterns)
