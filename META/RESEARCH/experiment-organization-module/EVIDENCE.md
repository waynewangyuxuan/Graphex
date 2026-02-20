# Evidence: Experiment Organization Patterns

## Source 1: KGGen (stair-lab/kg-gen)

**Structure**:
- `src/kg_gen/` — Library code: kg_gen.py, steps/_1_get_entities.py, _2_get_relations.py, _3_deduplicate.py
- `experiments/MINE/` — Benchmark runner: _1_evaluation.py, _2_compare_results.py, _3_visualize.py
- `experiments/MINE/results/{model-config}/` — Results per model config (.gitignored)
- `tests/` — Unit tests with fixture data in tests/data/

**Key pattern**: Numbered scripts (`_1_`, `_2_`, `_3_`) enforce execution order.
Results saved to `results/{model-config}/` — model name IS the config identifier.

**Runner interface** (experiments/MINE/_1_evaluation.py):
```python
python _1_evaluation.py --model openai/gpt-5-nano --evaluation-model local
# → results/{model-config}/results_{i}.json, kg_{i}.json
```

Model and params passed as CLI args, not hardcoded. Results include both
the generated KG (kg_{i}.json) and evaluation scores (results_{i}.json).

**Compare script** (experiments/MINE/_2_compare_results.py):
Reads ALL results/{model-config}/ directories, generates:
- results/results.png — comparison plot
- results/summary.txt — statistics and rankings

## Source 2: AI2 Tango (allenai/tango)

**Structure**:
- `tango/` — Core library (steps, integrations, executors)
- `examples/eval_p3/` — Example experiment with config.jsonnet + eval.py
- `test_fixtures/` — Test data separate from experiment data

**Key pattern**: Experiments defined as DAGs of typed steps in config files.
Each step has typed inputs/outputs, results are cached and reusable.

```jsonnet
// examples/eval_p3/config.jsonnet
"eval_xsum": {
    "type": "rouge_score",
    "input": {"ref": "generation_xsum"},  // references another step's output
}
```

**Takeaway for Graphex**: We don't need Tango's full DAG framework, but the
principle of config-driven step composition is valuable. A YAML config that
specifies extraction → resolution → evaluation as a pipeline with params.

## Source 3: PyKEEN (pykeen/pykeen)

**Key pattern**: Curated "experiment configurations" for reproducing published results.
```bash
pykeen experiments reproduce tucker balazevic2019 fb15k
```
Each experiment config specifies: model, dataset, training params, evaluation metrics.
All configs are committed; results are reproducible from config alone.

## Source 4: MLXP Framework

**Key pattern**: Two reserved directories — `config/` (YAML) and `logs/` (auto-generated).
Each run gets a unique subdirectory in logs/ named by execution order.
Config is automatically serialized alongside results for reproducibility.

## Graphex Current State Inventory

Files that should be REMOVED from src/ (superseded by CocoIndex spike approach):
- `src/pipeline/pipeline.py` — original multi-agent pipeline (ADR-0001, superseded by ADR-0003)
- `src/pipeline/enhanced_pipeline.py` — three-phase enhancement (also superseded)
- `src/pipeline/state.py` — pipeline state for old pipeline
- `src/agents/first_pass_agent.py` — FirstPass filtering (superseded)
- `src/agents/grounding_verifier.py` — grounding verification (superseded)
- `src/agents/entity_extractor.py` — old entity extractor (superseded)
- `src/agents/relation_extractor.py` — old relation extractor (superseded)
- `src/agents/validator.py` — old validator (superseded)
- `src/agents/base.py` — old agent base class (superseded)
- `src/context/context_builder.py` — old context builder (superseded)
- `src/context/entity_registry.py` — old entity registry (superseded)

Files that should be MOVED from examples/ to experiments/:
- `examples/test_enhanced_pipeline.py` → archive or delete
- `examples/test_improved_extraction.py` → archive or delete
- `examples/test_pdf_extraction.py` → archive or delete
- `examples/example_extraction.py` → archive or delete
- `examples/output/` → archive or delete

Files that should be PROMOTED from benchmark/scripts/ to src/:
- Extraction logic in `cocoindex_spike.py` → `src/extraction/structured_extractor.py`
- Evaluation logic (currently inline) → `src/evaluation/evaluator.py`
