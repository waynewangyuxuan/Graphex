# ADR-0003: CocoIndex-Style Structured Extraction

- **Status**: Accepted
- **Date**: 2026-02-19
- **Deciders**: Wayne

## Context

现有的 multi-agent pipeline（ADR-0001）在 threads-cv benchmark 上表现不佳：
- 核心节点召回率 37.5%
- 核心边召回率 25%
- 76% 的边被标记为 RelatedTo（无信息量）
- 噪声实体问题：把文件名（main-two-cvs-if.c）和作者名（ARPACI-DUSSEAU）当作实体提取

我们评估了 [CocoIndex](https://cocoindex.io/)（开源 AI 数据转换框架，Rust 核心 + Python API）作为替代方案。CocoIndex 的核心模式是 **单次结构化 LLM 提取**（`ExtractByLlm`），在一次调用中同时提取 entities + relationships。

## Decision

采用 **CocoIndex 风格的单次结构化提取**替代现有的 multi-agent 分步提取，作为 Graphex 提取管线的核心模式。

具体变更：
1. **提取层**：每个 chunk 一次 LLM 调用，同时输出 entities 和 relationships（JSON 结构化输出）
2. **保留后处理层**：FirstPass 过滤 + Entity Resolution 合并，作为提取后的精度提升手段
3. **暂不引入 CocoIndex 框架本身**：当前环境限制（需要 PostgreSQL + Python ≥3.11），且增量处理尚非 MVP 需求。提取模式先自行实现，后续可迁移到 CocoIndex 框架

### Spike 结果（threads-cv benchmark）

| 指标 | Multi-Agent Pipeline | CocoIndex Spike |
|---|---|---|
| 核心节点召回 | 37.5% (3/8) | **100% (8/8)** |
| 全部节点召回 | ~35% | **100% (17/17)** |
| 核心边召回 | 25% (2/8) | **50% (4/8)** |
| RelatedTo 占比 | 76% | 0.7% |
| 提取实体数 | 19 | 113（未充分去重） |

## Alternatives Considered

### Alternative 1: 继续优化 Multi-Agent Pipeline
- **Pros**: 不需要架构变更，Prompt 优化空间仍存在
- **Cons**: 分步提取的结构性缺陷——Relation Extractor 看不到其他 chunk 的实体上下文，容易退化为 RelatedTo
- **Why not**: Spike 显示单次结构化提取在相同 prompt 质量下已显著优于分步方案

### Alternative 2: 直接集成 CocoIndex 框架
- **Pros**: 增量处理、可视化调试器、Neo4j 导出等生产级功能
- **Cons**: 需要 PostgreSQL + Python ≥3.11；增量处理非 MVP 需求；耦合度高
- **Why not**: MVP 阶段优先验证提取质量，框架级集成推迟到 P1

## Consequences

### Positive
- 核心节点召回率从 37.5% 跳到 100%
- RelatedTo 边占比从 76% 降到 <1%
- 提取代码大幅简化（单次调用 vs 多 agent 编排）

### Negative
- 实体去重压力增大（113 个原始实体 vs 17 个 Ground Truth）
- 需要加强 Entity Resolution 和 FirstPass 过滤
- 放弃了 multi-agent 架构的可解释性优势（每步可独立审查）

### Risks
- **Token 成本**：单次调用要求更大的 output token，但省去了 FirstPass + EntityExtractor + RelationExtractor 的多次调用
- **Entity Resolution 瓶颈**：如果去重做不好，下游图谱质量仍会受损 → 下一步重点攻关

## Related

- [ADR-0001: Multi-Agent Pipeline Architecture](ADR-0001-multi-agent-pipeline-architecture.md)
- [ADR-0002: Gleaning and Entity Resolution](ADR-0002-gleaning-and-entity-resolution.md)
- [CocoIndex GitHub](https://github.com/cocoindex-io/cocoindex)
- [Spike 脚本](../../benchmark/scripts/cocoindex_spike.py)
- [Spike 评估结果](../../benchmark/datasets/papers/threads-cv/cocoindex_spike_eval.json)
