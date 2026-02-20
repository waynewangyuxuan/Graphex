# Architecture Decision Records

This folder contains Architecture Decision Records (ADRs) documenting significant technical decisions.

## What is an ADR?

An ADR captures a single architectural decision, including:
- The context and problem we faced
- The decision we made
- Alternatives we considered
- Consequences (both positive and negative)

## How to Write an ADR

1. Copy `_TEMPLATE.md` to `ADR-{NEXT_NUMBER}-{kebab-case-title}.md`
2. Fill in all sections
3. Set status to "Proposed"
4. Get review from relevant stakeholders
5. Update status to "Accepted" once approved

## ADR Numbering

ADRs are numbered sequentially: ADR-0001, ADR-0002, etc.
Never reuse numbers, even if an ADR is deprecated.

## ADR Lifecycle

```
Proposed → Accepted → [Deprecated | Superseded]
```

- **Proposed**: Under discussion
- **Accepted**: Decision is final and in effect
- **Deprecated**: No longer applies (explain why in the ADR)
- **Superseded**: Replaced by a newer ADR (link to it)

## Index

| Number | Title | Status | Date |
|--------|-------|--------|------|
| [ADR-0001](ADR-0001-multi-agent-pipeline-architecture.md) | Multi-Agent Pipeline Architecture | Proposed | 2026-02-01 |
| [ADR-0002](ADR-0002-gleaning-and-entity-resolution.md) | Gleaning and Description-Aggregation Entity Resolution | Proposed | 2026-02-18 |
| [ADR-0003](ADR-0003-cocoindex-style-structured-extraction.md) | CocoIndex-Style Structured Extraction | Accepted | 2026-02-19 |
| [ADR-0004](ADR-0004-embedding-entity-resolution.md) | Embedding-Based Entity Resolution (iText2KG Pattern) | Superseded | 2026-02-19 |
| [ADR-0005](ADR-0005-graphiti-cascading-er.md) | Graphiti-Style Cascading Entity Resolution | Accepted | 2026-02-20 |
