# Progress Log

Append-only development log. Add new entries at the top.

---

## 2026-02-20

### Completed
- **Entity Resolution Phase 1: iText2KG Embedding Approach (ADR-0004)**
  - 创建 `src/resolution/entity_resolver.py` — 基于 embedding cosine similarity 的去重
  - 创建 `src/resolution/parallel_merge.py` — O(log N) 二叉归约合并（ThreadPoolExecutor）
  - 使用 sentence-transformers (`all-MiniLM-L6-v2`) 编码实体 label+type+definition
  - Union-Find 聚类，阈值可调
  - 接入 `benchmark/scripts/cocoindex_spike.py`（通过 `parallel_merge()`）

- **Embedding ER 实验结果（threads-cv）**
  - θ=0.8: 113→78 entities — under-merge，大量重复未被捕获
  - 加入 definition 到 embedding 输入 — 无改善，仍然 78 entities
  - θ=0.6: 113→24 entities — **灾难性 over-merge**
    - wait(), signal(), Lock, Mutex 全部合并为同一实体
    - 核心节点召回从 62.5% 暴跌至 12.5%
  - **根因分析**: embedding cosine similarity 对短实体名不可靠，"Lock"、"Mutex"、"Thread" 在语义空间中距离太近

- **Entity Resolution Phase 2: Graphiti 三层级联方法 (ADR-0005, supersedes ADR-0004)**
  - 重写 `src/resolution/entity_resolver.py` — 完全替换 embedding 方案
  - Layer 1: Exact normalized match (HashMap O(1))
  - Layer 2: Entropy-gated 3-gram character Jaccard (θ=0.9)
    - Shannon 熵值门控：短名称（"Lock"、"API"）跳过模糊匹配，直接送 LLM
    - 高熵名称（"Condition Variable"、"Bounded Buffer"）走 Jaccard 匹配
  - Layer 3: LLM batch dedup — 所有未解决的单例实体一次性送 LLM 分组
  - 无新外部依赖（Layer 1-2 纯 Python 字符串操作，Layer 3 使用现有 litellm）

- **Graphiti ER 实验结果（threads-cv）**

| 指标 | CocoIndex 无 ER | Embedding θ=0.8 | Embedding θ=0.6 | Graphiti 级联 | 目标 |
|---|---|---|---|---|---|
| 提取实体数 | 113 | 78 | 24 | **67** | ~20 |
| 核心节点召回 | 100% | 62.5% | 12.5% | **50%** | >60% |
| 全部节点召回 | 100% | — | — | **64.7%** | — |
| 核心边召回 | 50% | — | — | **25%** | >60% |
| over-merge 问题 | 无 | 无 | **严重** | 无 | — |

- **4 个 Missing Core Nodes 分析** — 非 ER 问题，是提取/评估层面的 gap：
  - "lock/mutex" vs "Mutex Lock"（词序不匹配）
  - "producer/consumer problem" vs "Producer/Consumer Solution"（用词差异）
  - "bounded buffer" — 未被提取
  - "use while loop rule" vs "Use while loop instead of if statement"（无子串匹配）

- **Chunk Size 优化：512 chars → 6000 chars (~128 tokens → ~1500 tokens)**
  - 发现 `length_function=len` 导致 chunk_size=512 实际是 512 字符 ≈ 128 tokens（远低于预期）
  - 参考各项目 chunk size：GraphRAG 300-600t, LightRAG 1200t, RAGFlow 4096t, KGGen 整文档
  - 调整为 6000 chars (~1500 tokens)，overlap 等比放大到 900 chars (~15%)
  - threads-cv 从 ~30 chunks 降至 ~5 chunks

- **Chunk Size 优化实验结果（threads-cv，含 Graphiti ER）**

| 指标 | 512 chars + Graphiti | **6000 chars + Graphiti** | 目标 |
|---|---|---|---|
| 提取实体数 | 67 | **18** | ~20 |
| 核心节点召回 | 50% (4/8) | **87.5% (7/8)** | >60% |
| 全部节点召回 | 64.7% (11/17) | **70.6% (12/17)** | — |
| 核心边召回 | 25% (2/8) | **37.5% (3/8)** | >60% |
| 全部边召回 | 13.3% (2/15) | **26.7% (4/15)** | — |
| Input tokens | 54,714 | **14,649** | — |
| Output tokens | 33,979 | **5,314** | — |

- **关键改善分析**：
  - 之前 4 个 missing core nodes 中 3 个被解锁（Lock/Mutex, Bounded Buffer, Producer/Consumer Problem）
  - 唯一剩余 miss: "Use While Loop Rule" — 实际已被提取为 "Always use while loops when waiting on a condition variable"，但 eval 子串匹配无法捕获
  - 实体数从 67→18，精准命中目标范围
  - Token 消耗降低 ~75%（更少的 chunks = 更少的 LLM 调用）

- **边召回瓶颈分析**：
  - 匹配的 4 条边：wait()→CV PartOf, signal()→CV PartOf, Mesa→Hoare Contrasts, CV→P/C Enables
  - 方向反转导致 miss：GT 说 Bounded Buffer→P/C (PartOf)，提取出 P/C→Bounded Buffer (PartOf)
  - Producer Thread / Consumer Thread 未单独提取 → 阻断 4 条边
  - "While Loop Rule" 节点 miss → 阻断 Mesa→While Loop Rule (Causes) 核心边

- **Repo 重构：Config-Driven Experiment Organization (ADR-0007)**
  - 从 `cocoindex_spike.py` 提取逻辑到 `src/extraction/` 和 `src/evaluation/`
  - 删除死代码：`src/agents/` (6 files), `src/pipeline/` (4 files), `src/context/` (3 files), `examples/` (5 files)
  - 创建 `experiments/` 目录：`configs/` (v1-v5 YAML), `runners/`, `results/` (.gitignored)
  - `src/extraction/prompts.py` 支持多 prompt 变体 (PROMPTS registry: "chunk", "whole_doc")
  - `extract_chunk()` 新增 `prompt` 参数，支持 config 驱动的 prompt 选择
  - 修复 4 个 pre-existing test failures (chunker defaults, RELATED_TO removal)
  - 净减 3,435 行代码，新增 702 行

- **v6 整文档提取实验（Whole-Document Extraction）**
  - 假设：Gemini 2.5 Flash Lite 有 1M 上下文，threads-cv 仅 ~9k tokens，可一次性提取
  - 首次尝试（chunk prompt）：12 entities, 75% core node recall — LLM 过于保守
  - 创建 `WHOLE_DOC_PROMPT`：强调 "Be thorough"，提示 15-25 entities，去掉 "quality over quantity"
  - 优化后结果显著改善

| 指标 | v5 分块+ER | v6 整文档(chunk prompt) | **v6 整文档(whole_doc prompt)** | 目标 |
|---|---|---|---|---|
| 实体数 | 40 | 12 | **20** | ~17 |
| 核心节点召回 | 87.5% (7/8) | 75% (6/8) | **87.5% (7/8)** | >60% |
| 全部节点召回 | 88.2% (15/17) | 47.1% (8/17) | **70.6% (12/17)** | — |
| 核心边召回 | 50% (4/8) | 25% (2/8) | **37.5% (3/8)** | >60% |
| LLM 调用次数 | 8+1(ER) | **1** | **1** | — |
| Input tokens | 14,657 | 11,409 | **11,504** | — |
| Output tokens | 9,153 | 1,438 | **2,481** | — |

- **v6 实体质量深度分析**
  - 20 个实体全部零噪声，额外提取的 broadcast(), Covering Condition, Spurious Wakeup 等都合理
  - Label 不匹配导致 eval miss："Wait Must Re-check Condition" = GT "Use While Loop Rule"；"Spinning" = GT "Spin-based Waiting"
  - Producer Thread / Consumer Thread 未单独提取，被归入 P/C Problem definition

- **v6 边质量深度分析 — 主要瓶颈**
  - 使用了非法边类型 `"Claim"`（应为实体类型）— Flash Lite 指令遵循弱
  - 方向反转：P/C→CV (Enables) 提取反了，GT 是 CV→P/C (Enables)
  - 语义类型错误：State Variable→CV 标为 "Before"（应为 Enables），CV→Lock 标为 "PartOf"（GT 为 Enables）
  - 实际匹配 GT 的边仅 4 条：wait()→CV PartOf, signal()→CV PartOf, Bounded Buffer→P/C PartOf, Mesa→Hoare Contrasts

### Decisions Made
- **Abandon embedding cosine similarity for ER** — 无法在 under-merge 和 over-merge 之间找到平衡点（ADR-0004 → Superseded）
- **Adopt Graphiti-style cascading ER** — 确定性优先、LLM 兜底的三层方法 (ADR-0005)
- **Chunk size 从 512 chars 提升至 6000 chars** — 根因是 `length_function=len` 按字符计数，128 tokens 太碎导致实体爆炸
- Chunk size 是比 ER 更大的杠杆：源头减少碎片 > 下游修补重复
- **Repo 重构为 config-driven experiment organization** (ADR-0007) — src/ 只保留活跃代码，实验通过 YAML config 驱动
- **整文档提取可行但边质量受限** — 实体质量已达标（20 entities, 87.5% core recall），但边的方向和类型判断是 Flash Lite 模型能力瓶颈

### Blockers / Issues
- 边召回仍未达标（37.5% core vs 目标 >60%）— 根因是 Flash Lite 的边类型/方向判断弱，非 prompt 可完全解决
- Eval 子串匹配过于严格 — "Wait Must Re-check Condition" vs "Use While Loop Rule" 无法匹配
- Flash Lite 产出非法 edge type（"Claim" 作为边类型）— 需要后处理校验或更强模型

### Next
- [ ] 增强 eval 匹配逻辑（模糊匹配 / synonym 映射 / 双向边匹配），减少假阴性
- [ ] 边方向归一化：PartOf 等方向敏感的边类型考虑双向匹配或规范化
- [ ] 边质量提升策略：用更强模型（Flash / Pro）做边提取，或加 edge-level 后处理校验
- [ ] 清理 requirements.txt 中不再需要的 embedding 依赖
- [ ] 在 MiroThinker 和 threads-bugs 上验证泛化性

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
- [x] 增强 Entity Resolution：语义去重 → 完成，见 2026-02-20（ADR-0004 → ADR-0005）
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
