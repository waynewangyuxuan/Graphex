# ADR-0006: Tiered Model Strategy

- **Status**: Proposed
- **Date**: 2026-02-20
- **Deciders**: Wayne

## Context

Our extraction pipeline makes multiple LLM calls per document (extraction, entity resolution,
validation). Currently all calls use the same model (Gemini 2.0 Flash). However:

1. Different pipeline stages have very different output sizes and quality requirements
2. Output tokens cost 4-6x more than input tokens across all providers
3. Entity resolution only needs Yes/No answers (~5 tokens output) but needs strong judgment
4. Entity extraction generates 500-800 output tokens per chunk — cost-sensitive at scale

By matching model capability to task requirements, we can improve quality on critical
decisions while reducing overall cost.

## Decision

Use different models for different pipeline stages, selected by output volume and
quality sensitivity:

| Stage | Output Size | Quality Need | Model | Cost (per 1M out) |
|-------|------------|-------------|-------|-------------------|
| Doc Context Generation | ~150 tokens | Medium | Flash-Lite | $0.40 |
| Entity Extraction | 500-800 tokens | Medium | Flash-Lite | $0.40 |
| Relation Extraction | 300-500 tokens | Medium | Flash-Lite | $0.40 |
| Entity Resolution | 5-10 tokens/pair | **High** | 2.5 Flash | $2.50 |
| Validation / Summary | 100-200 tokens | **High** | 2.5 Flash | $2.50 |

Estimated cost per 15K-token paper: $0.03-0.05 (vs ~$0.02 all-Flash-Lite).

Model selection is specified in experiment config YAML, not hardcoded:

```yaml
models:
  extraction: "gemini/gemini-2.5-flash-lite"
  resolution: "gemini/gemini-2.5-flash"
  validation: "gemini/gemini-2.5-flash"
```

## Alternatives Considered

### Alternative 1: Single Model for Everything
- **Pros**: Simple, no routing logic
- **Cons**: Overpaying on extraction OR under-quality on resolution
- **Why not**: ER quality is critical (Lock vs Mutex), extraction is cost-sensitive

### Alternative 2: Use DeepSeek V3 for Extraction
- **Pros**: Cheapest output ($0.28/M), good structured output
- **Cons**: 128K context (sufficient but less headroom), API stability concerns
- **Why not**: Viable as future option, but Gemini ecosystem consistency preferred for MVP

### Alternative 3: Use Stronger Model Everywhere (2.5 Flash)
- **Pros**: Best quality across the board
- **Cons**: 6x more expensive on output-heavy extraction calls
- **Why not**: Cost scales with document count; unnecessary for extraction where Flash-Lite is sufficient

## Consequences

### Positive
- Better ER quality on critical judgments (Lock ≈ Mutex) at negligible cost increase
- Extraction cost stays low for the bulk of LLM calls
- Config-driven model selection enables easy A/B testing of models

### Negative
- Slightly more complex pipeline (model routing)
- Two API keys / model endpoints to manage (both Google, so minimal)

### Risks
- Flash-Lite extraction quality might be insufficient → mitigated by config: easy to swap
- Model pricing changes → configs make it easy to adjust

## Related

- ADR-0003: CocoIndex-Style Structured Extraction (defines the extraction approach)
- ADR-0005: Graphiti Cascading ER (defines the resolution approach that benefits from stronger model)
- Meta/Research/entity-extraction-module/INTEGRATION_GUIDE.md (cost analysis)
