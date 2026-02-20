# Integration Guide: Repo Restructuring

## Problem → Solution Map

| Problem | Root Cause | Solution |
|---------|-----------|----------|
| Dead code in src/ | Pipeline approach changed 3x but old code remains | Remove superseded code, keep in git history |
| Spike script = monolith | cocoindex_spike.py has extraction + eval + merge + CLI | Factor into src/ library functions |
| Params hardcoded | chunk_size, model, thresholds in .py files | Extract to YAML experiment configs |
| examples/ = graveyard | Old test scripts never cleaned up | Delete; experiments/ replaces this role |
| Can't reproduce past runs | No record of which params produced which results | Config files committed, results reproducible |

## Migration Plan

### Step 1: Clean src/ (remove dead code)

Delete these directories/files entirely (git history preserves them):

```
src/agents/              ← entire directory (all agents superseded by structured extraction)
src/pipeline/pipeline.py
src/pipeline/enhanced_pipeline.py
src/pipeline/state.py
src/pipeline/__init__.py ← rewrite to export nothing or remove
src/context/             ← entire directory (context_builder + entity_registry superseded)
examples/                ← entire directory
```

Keep:
```
src/chunking/            ← active, just updated chunk_size
src/parsing/             ← active, PDF parsing still used
src/resolution/          ← active, Graphiti cascading ER
src/schema/              ← active, node/edge schema
src/utils/               ← active, ID generation
```

### Step 2: Promote spike logic to src/

Extract from cocoindex_spike.py into proper modules:

```
src/extraction/
  __init__.py
  structured_extractor.py  ← extract_chunk() function (the core LLM call)
  prompts.py               ← EXTRACTION_INSTRUCTION, schema definitions
  merger.py                ← merge_chunk_results() logic

src/evaluation/
  __init__.py
  evaluator.py             ← compare output vs ground_truth.json
  metrics.py               ← recall, precision, F1 calculations
```

### Step 3: Create experiment infrastructure

```
experiments/
  configs/
    baseline_v1.yaml       ← original 512-char chunks, no ER
    v2_embedding_er.yaml   ← embedding ER (θ=0.8), superseded
    v3_graphiti_er.yaml    ← Graphiti cascading ER, 512 chars
    v4_large_chunk.yaml    ← 6000 chars + Graphiti ER (current best)
    v5_two_pass.yaml       ← planned: KGGen-style two-pass extraction
  runners/
    run_extraction.py      ← load config → chunker → extractor → resolver → save
    run_evaluation.py      ← load output + ground_truth → metrics → save
    compare.py             ← read all results/ dirs → comparison table
  results/                 ← .gitignored; reproduced from config + runner
```

### Step 4: Retroactively create configs for past experiments

Even though we didn't have configs before, create them now as documentation:

```yaml
# experiments/configs/baseline_v1.yaml
experiment:
  name: "baseline-v1"
  date: "2026-02-19"
  description: "CocoIndex-style single-call extraction, 512-char chunks, no ER"
  status: "superseded_by: v4_large_chunk"

extraction:
  model: "gemini/gemini-2.0-flash"
  chunk_size: 512
  chunk_overlap: 75
  mode: "single_pass"

resolution:
  method: "none"

results_summary:
  threads_cv:
    entities: 113
    core_node_recall: 1.0
    core_edge_recall: 0.5
```

This creates a queryable history of what was tried and what worked.

## Target Directory Structure

```
Graphex/
├── src/                    # Library code (clean, tested, current approach only)
│   ├── extraction/         # LLM-based entity/relation extraction
│   ├── resolution/         # Entity resolution (cascading ER)
│   ├── chunking/           # Document chunking
│   ├── parsing/            # PDF parsing
│   ├── evaluation/         # Benchmark evaluation metrics
│   ├── schema/             # Node/Edge type definitions
│   └── utils/              # ID generation, helpers
├── experiments/            # Experiment orchestration
│   ├── configs/            # YAML configs (versioned, committed)
│   ├── runners/            # Scripts that load config + call src/
│   └── results/            # .gitignored output artifacts
├── benchmark/              # Ground truth + datasets (stable, committed)
│   ├── datasets/           # Source PDFs + ground_truth.json per dataset
│   ├── templates/          # Evaluation and ground truth templates
│   └── visualizations/     # Generated visualizations
├── Meta/                   # Documentation (unchanged)
└── tests/                  # Unit tests for src/
```

## Verification Checklist

- [ ] `src/` contains only active code (no dead pipeline/agents)
- [ ] `examples/` directory removed
- [ ] Every past experiment has a corresponding YAML config
- [ ] `experiments/runners/run_extraction.py` can reproduce v4 results from config
- [ ] `experiments/results/` is in .gitignore
- [ ] `pytest` still passes after restructuring
- [ ] Progress.md updated with restructuring decision
