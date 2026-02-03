# ADR-0001: Multi-Agent Pipeline Architecture

- **Status**: Proposed
- **Date**: 2026-02-01
- **Deciders**: Team

## Context

We need to extract knowledge graphs from long documents (PDFs, papers). This requires:
1. Document parsing and chunking (context window limits)
2. Entity extraction from text
3. Relation extraction between entities
4. Validation and quality control
5. Cross-chunk entity resolution

The question is: how should we architect the AI components?

## Decision

Use a **DAG pipeline with specialized agents** and central state management:

```
Pipeline Controller (orchestration)
    ↓
Entity Extractor Agent → Relation Extractor Agent → Validator Agent
    ↓
Entity Registry (shared state for cross-chunk resolution)
```

**MVP Implementation (4 Agents)**:
1. **Chunk Processor** - Prepares context for extraction
2. **Entity Extractor** - Identifies entities per chunk
3. **Relation Extractor** - Finds relationships
4. **Validator** - Checks quality, flags issues

**Key Design Principles**:
- Each agent has a single responsibility
- Shared state via Entity Registry
- Sequential processing per chunk (MVP), parallelizable later
- JSON output with structured schemas

## Alternatives Considered

### Alternative 1: Single Monolithic Agent
- **Pros**: Simpler, fewer API calls
- **Cons**: Harder to debug, can't optimize per task, worse at complex extractions
- **Why not**: Research shows specialized agents outperform generalist approaches for structured extraction

### Alternative 2: Fully Autonomous Agent Swarm
- **Pros**: More flexible, can self-organize
- **Cons**: Unpredictable, harder to debug, higher cost
- **Why not**: Too risky for MVP, need predictable outputs

### Alternative 3: LangGraph with Complex Routing
- **Pros**: Mature framework, good state management
- **Cons**: Additional dependency, learning curve
- **Why not**: Custom Python pipeline sufficient for MVP, can migrate later

## Consequences

### Positive
- Clear separation of concerns
- Each agent can be tested/tuned independently
- Entity Registry enables cross-chunk consistency
- Easy to add new agents (e.g., specialized extractors)

### Negative
- Multiple API calls per chunk (higher cost)
- Need to manage inter-agent communication
- More complex than single-prompt approach

### Risks
- **Risk**: Agent outputs may be inconsistent
  - **Mitigation**: Strict output schemas, validation agent, retries
- **Risk**: Entity Registry may miss duplicates
  - **Mitigation**: Embedding similarity + LLM verification

## Related

- [Technical.md](../Core/Technical.md) - Full architecture details
- [Node_Edge_Schema.md](../Research/Node_Edge_Schema.md) - Schema definitions
