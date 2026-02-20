# Experiment Organization for Research-Driven Projects

## Core Problem

Research-driven projects accumulate experimental code, results, and configs across
iterations. Without structure, experiments become unreproducible, dead code lingers,
and the "current best" approach is unclear.

## Pattern: Numbered Experiment Steps + Config-Driven Runs

**Source**: KGGen (NeurIPS'25), AI2 Tango, PyKEEN

### Key Insight

Separate three concerns that typically get tangled:

1. **Library code** (`src/`) — reusable, tested, stable
2. **Experiment scripts** (`experiments/`) — orchestration, transient, evolving
3. **Experiment results** (`results/` or gitignored output) — artifacts, reproducible via config

### Structure Pattern

```
src/                        ← Library: importable, tested, clean API
  extraction/               ← Extraction logic (two-pass, constrained relations)
  resolution/               ← ER logic (cascading, LLM dedup)
  chunking/                 ← Chunking logic
  parsing/                  ← PDF parsing
  evaluation/               ← Eval metrics (reusable across experiments)

experiments/                ← Experiment orchestration
  configs/                  ← YAML/JSON configs (committed, versioned)
    baseline.yaml           ← chunk_size, model, ER params, etc.
    v2_large_chunk.yaml
    v3_two_pass.yaml
  runners/                  ← Scripts that load config + call src/
    run_extraction.py       ← Main experiment runner
    run_evaluation.py       ← Evaluate output against ground truth
    compare_results.py      ← Cross-experiment comparison
  results/                  ← .gitignored, reproduced from config + runner

benchmark/                  ← Ground truth + datasets (committed, stable)
  datasets/
    threads-cv/
      source.pdf
      ground_truth.json
```

### Config-Driven Reproducibility

Every experiment run is defined by a YAML config:

```yaml
# experiments/configs/v2_large_chunk.yaml
experiment:
  name: "v2-large-chunk"
  description: "Test 1500-token chunks with Graphiti ER"

extraction:
  model: "gemini/gemini-2.5-flash-lite"
  chunk_size: 6000        # chars (~1500 tokens)
  chunk_overlap: 900
  mode: "single_pass"     # or "two_pass"

resolution:
  method: "cascading"     # exact → jaccard → llm
  jaccard_threshold: 0.9
  entropy_threshold: 1.5
  llm_model: "gemini/gemini-2.5-flash"  # stronger model for ER

evaluation:
  datasets: ["threads-cv"]
  match_mode: "fuzzy"     # or "exact", "semantic"
```

Runner loads config, calls src/ functions, writes results:

```python
# experiments/runners/run_extraction.py
config = yaml.load(args.config)
chunker = Chunker(chunk_size=config["extraction"]["chunk_size"])
# ... run pipeline, save to experiments/results/{config.name}/
```

### Dead Code Handling

**Rule**: `src/` only contains the CURRENT approach. Old approaches are:
- Documented in ADRs (decisions that led to them and why they were superseded)
- Removed from `src/` (git history preserves them)
- If needed for comparison, kept as a separate experiment config, not as parallel code paths

### Experiment Lifecycle

```
Hypothesis → Config (YAML) → Run → Results → Evaluate → ADR (if changing approach)
                                                 ↓
                                          Progress.md (log the outcome)
```

## Anti-Patterns to Avoid

1. **Spike scripts that grow into production** — cocoindex_spike.py should become
   a config + runner, not a monolithic script with hardcoded params
2. **Multiple pipeline implementations in src/** — enhanced_pipeline.py vs pipeline.py;
   pick one, archive the other
3. **examples/ as experiment graveyard** — test_enhanced_pipeline.py, test_improved_extraction.py
   are really experiments, not examples
4. **Params in code, not config** — chunk_size=512, model="gemini/..." should be in YAML

## Applicability to Graphex

**Current state**: One spike script, multiple dead pipelines, params in code.
**Target state**: Config-driven experiments, clean src/, reproducible runs.

Migration priority:
1. Clean src/ — remove dead code (old pipeline, old agents)
2. Move spike logic into src/ as library functions
3. Create experiment configs for each variation tested
4. Move benchmark evaluation into reusable src/evaluation/
