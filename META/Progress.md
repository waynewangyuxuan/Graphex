# Progress Log

Append-only development log. Add new entries at the top.

---

## 2026-02-19

### Completed
- 评估 CocoIndex（cocoindex.io）作为提取管线替代方案
  - 调研 CocoIndex 架构：Rust 核心 + Python API，增量处理，声明式数据流，Neo4j 集成
  - 环境限制：需要 Python ≥3.11 + PostgreSQL，当前 VM 无法直接运行
- 编写 CocoIndex 风格 Spike 脚本 (`benchmark/scripts/cocoindex_spike.py`)
  - 模拟 CocoIndex 的 `ExtractByLlm` 模式：单次 LLM 调用同时提取 entities + relationships
  - 使用 JSON 结构化输出，匹配 Graphex 的 Node/Edge Schema
  - 基础 label 去重 + 边去重
- 在 threads-cv benchmark 上运行 Spike 并完成评估
- 创建 ADR-0003: CocoIndex-Style Structured Extraction

### Spike 结果（threads-cv）

| 指标 | Multi-Agent Pipeline | CocoIndex Spike | 目标 |
|---|---|---|---|
| 核心节点召回 | 37.5% | **100%** | >60% |
| 全部节点召回 | ~35% | **100%** | — |
| 核心边召回 | 25% | **50%** | >60% |
| RelatedTo 占比 | 76% | 0.7% | <40% |
| 提取实体数 | 19 | 113 | ~17 |

### 关键发现
- **单次结构化提取显著优于多 agent 分步提取**：同时看到 entities + relationships 的上下文让 LLM 更好地理解关系语义
- **实体爆炸问题**：113 个实体（GT 17 个），原因是跨 chunk 去重只做了 label 精确匹配
- **噪声实体**：grep, wc, Quicksort, HTTP request 等非教学内容被提取
- **结论**：CocoIndex 做提取底座 + Graphex 做后处理增强（Entity Resolution + FirstPass 过滤）

### Decisions Made
- 采用 CocoIndex 风格的单次结构化提取替代 multi-agent 分步提取 (ADR-0003)
- MVP 阶段暂不引入 CocoIndex 框架本身，仅采用其提取模式
- 下一步重点：Entity Resolution 增强，解决实体爆炸问题

### Blockers / Issues
- VM 环境无法运行 CocoIndex（需 PostgreSQL + Python ≥3.11）
- Gemini API 在 VM 网络环境中被阻断（403），Spike 在本地运行

### Next
- [ ] 增强 Entity Resolution：语义去重（synonym matching, embedding similarity）
- [ ] 叠加 FirstPass 过滤到 Spike 脚本，减少噪声实体
- [ ] 验证后处理后的最终指标（目标：实体数 ~20, 核心边召回 >60%）
- [ ] 在 MiroThinker 和 threads-bugs 上跑 Spike 验证泛化性

---

## 2026-02-18

### Completed
- Applied Prism knowledge module `kg-extraction-pipeline` (GraphRAG + nano-graphrag patterns)
  - Created `Meta/Research/KG_Pipeline_Patterns.md` — Graphex-specific pattern digest
  - Created `Meta/Decisions/ADR-0002` — Gleaning + Entity Resolution adoption decision
  - Updated `Meta/Core/Technical.md` — §3.3 Gleaning spec, §4.4 Phase 4 Entity Resolution strategy
- Began implementation of P0 patterns in `src/pipeline/`

### Decisions Made
- **Gleaning**: `max_gleanings` is adjustable (not hardcoded); start at 1; only on chunks >500 tokens
- **P1 patterns** (Community Detection, Storage Abstraction): documented in KG_Pipeline_Patterns.md only; not yet integrated into Technical.md roadmap

### Blockers / Issues
- None

### Next
- [ ] Run benchmark (threads-cv) after Gleaning + Entity Resolution implementation
- [ ] Target: core node recall >60%
- [ ] If P0 sufficient, plan P1: Community Detection (graspologic/Leiden)

---

## 2026-02-12

### Completed
- 建立 Benchmark 系统
  - 创建 `benchmark/` 目录结构
  - 创建 Ground Truth 模板 (`ground_truth_template.json`, `evaluation_template.md`)
  - 为三篇测试文档创建 Ground Truth:
    - threads-cv: 17 nodes, 17 edges (8 core each)
    - MiroThinker: 22 nodes, 22 edges (12 core each)
    - threads-bugs: 20 nodes, 20 edges (10 core each)
- 完成 Pipeline 问题诊断
  - 对比 threads-cv 系统输出 vs Ground Truth
  - 核心节点匹配率: 37.5%
  - 核心边匹配率: 25%
  - 识别 6 个主要问题根因
- 创建系统性文档
  - `benchmark/PIPELINE_DIAGNOSIS.md` - 问题诊断报告
  - `Meta/Research/Prompt_Engineering_Log.md` - Prompt 优化追踪日志

### 关键发现

**Entity Extraction 问题**:
| 问题 | 影响 |
|------|------|
| 无噪声过滤规则 | 提取文件名、作者名作为实体 |
| 缺少 Method 类型 | 无法表示 wait(), signal() 等核心操作 |
| 无重要性标注 | 核心概念和边缘提及混淆 |

**Relation Extraction 问题**:
| 问题 | 影响 |
|------|------|
| 边类型选择指南缺失 | 76% 边都是 RelatedTo |
| 无 Enables/Contrasts 使用 | 缺失关键关系类型 |

### Decisions Made
- 建立 Prompt Engineering 实验追踪体系 (EXP-XXX 编号)
- 优先 Prompt 优化 (P0) 而非架构改动
- 目标指标: 核心节点匹配 >70%, RelatedTo <40%

### Blockers / Issues
- 无

### Next
- [ ] 执行 EXP-002: Entity Extractor Prompt v0.2
- [ ] 执行 EXP-003: Relation Extractor Prompt v0.2
- [ ] 重新运行 benchmark 验证改进效果
- [ ] 如果 Prompt 优化效果不足，考虑架构改进 (First-Pass Agent)

---

## 2026-02-01

### Completed
- Project structure initialized with Meta folder hierarchy
- Existing documentation migrated (Product.md, Technical.md, Research docs)
- ADR system set up
- Milestone tracking system created

### Decisions Made
- Focus on core business logic testing before frontend development
- MVP targets Node/Edge schema validation and AI pipeline testing

### Blockers / Issues
- None

### Next
- Begin M1: Core pipeline implementation and testing
- Validate Node/Edge schema with real documents
- Test AI extraction workflow

---

<!-- Template for new entries:

## YYYY-MM-DD

### Completed
-

### Decisions Made
-

### Blockers / Issues
-

### Next
-

-->
