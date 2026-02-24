# Progress Log

Append-only development log. Add new entries at the top.

---

## 2026-02-24

### Completed

- **Marker PDF Parser Integration**
  - `src/parsing/marker_parser.py`: MarkerParser class with lazy model loading, `force_ocr` and `use_llm` options
  - `src/parsing/pdf_parser.py`: Added `create_parser(backend)` factory — auto-detects marker availability, falls back to PyMuPDF
  - `experiments/eval/run_eval.py`: Added `--parser auto|pymupdf|marker` CLI flag
  - `Meta/Research/PDF_Parsing_Upgrade.md`: Research doc with comparison, config guide, and validation plan
  - 动机：Adam 论文 53 个 U+FFFD 字符 + 数学符号导致 JSON 损坏，根因是 PyMuPDF 无法处理复杂 math glyphs
  - Marker 基于 Surya OCR，学术论文支持：math→LaTeX, dual-column layout, table structure

### Decisions Made
- **Marker 作为可选 PDF parser** — 通过 factory pattern 支持 auto/pymupdf/marker 三种 backend
- **Lazy model loading** — Marker 模型 ~3GB，首次调用时加载，singleton 复用
- **force_ocr=True 为默认** — 必须开启才能处理 inline math

### Next
- [ ] 安装 marker-pdf，用 Adam 论文验证 math 质量改善
- [ ] Phase 1 全量重跑对比 PyMuPDF vs Marker
- [ ] 检查 LaTeX 格式对 extraction prompt 的影响

---

## 2026-02-23

### Completed

- **Phase 1 Evaluation: 10 CS Papers 跑通**
  - 创建完整评估框架：`experiments/eval/test_corpus.py`（10 CS + 5 跨学科 + 3 多文档组）
  - 创建 7 维评分体系：`experiments/eval/scoring_rubric.py`（narrative_coverage, segment_quality, relation_accuracy, tree_structure, concept_extraction, dedup_quality, anchor_binding）
  - 创建批量运行器：`experiments/eval/run_eval.py`（下载、单篇运行、分阶段运行）
  - 10 篇 CS 论文全部成功提取 + tree 构建

- **Tree Structuring 修复（3 个 bug）**
  - Bug 1: `max_tokens=4096` 硬编码 → 长文档（>60 segs）的 tree JSON 输出被截断，`_parse_json` 返回空 dict
    - 修复：动态计算 `max_tokens = max(4096, segments * 50 + 500)`，上限 16384
    - 加入 retry：首次返回空时自动用 16384 重试
    - 加入 `finish_reason=length` 检测和 warning 输出
  - Bug 2: LLM 返回循环 branches（如 s3→s5, s5→s3）导致 `build_node()` 无限递归（RecursionError）
    - 修复：构建 `children_of` 后做 cycle detection，主动断开循环边
    - 加入 `_building` set 作为 recursion guard（最终安全网）
    - 过滤 spine nodes 不能作为 branch children
  - Bug 3: self-loop（parent_id == child_id）未处理 → 直接跳过

- **Chunk Size 问题诊断与修复（3 轮迭代）**

  **迭代 1：发现 segment 过多**
  - 问题：dropout 107 segs、raft 118 segs、resnet 89 segs — 每段仅 ~220 chars（1-2 句话）
  - 根因：`DEFAULT_CHUNK_TOKENS = 2048`（~8000 chars），长论文切出 10+ chunks，每个 chunk 产出 10+ segments
  - 措施：将 `DEFAULT_CHUNK_TOKENS` 从 2048 提高到 6000
  - 结果：attention 69→29 segs，resnet 89→38 segs ✓，但 dropout 107→82、bert 61→65 仍偏多

  **迭代 2：发现 per-chunk 产出不均**
  - 问题：chunk 1 统一产出 29-35 个 segments，后续 chunks 仅 11-20 个
  - 根因：第一个 chunk 没有 "existing segments" 做去重参照，LLM 缺少粒度锚定
  - 措施：修改 extraction prompt — "aim for 5-8 segments per section, each covering a complete argumentative unit. If producing more than 10, merge related details."
  - 结果：改善但问题转移到 chunk 数量线性增长

  **迭代 3：Adaptive Chunking（对数缩放）**
  - 问题：chunk 数量随文档长度线性增长 → segment 数量线性增长。但叙事复杂度不是线性的。
  - 用户洞察："20K token 的文章只应该比 10K token 的文章多 30% segment，不是两倍"
  - 措施：重写 `programmatic_chunker.py` — chunk count = log2(doc_tokens / 5000) + 1
    - 考虑 overlap 补偿和段落断点的额外空间
    - 实际效果：5K→1 chunk, 10K→2, 15K→3, 20K→3, 50K→4
  - 最终结果（Phase 1 全部 10 篇）：

  | Paper | Tokens | Chunks | Segs | Spine/Branch | Acts |
  |-------|--------|--------|------|-------------|------|
  | attention | 10K | 2 | 31 | 17/14 | 5 |
  | resnet | 15K | 3 | 42 | 20/22 | 5 |
  | gan | 7K | 2 | 19 | 9/10 | 4 |
  | bert | 16K | 3 | 47 | 24/23 | 4 |
  | dropout | 20K | 3 | 44 | 20/24 | 7 |
  | mapreduce | 14K | 2 | 31 | 16/15 | 5 |
  | bitcoin | 5K | 1 | 21 | 16/5 | 4 |
  | raft | 23K | 3 | 64 | 32/32 | 7 |
  | batchnorm | 11K | 2 | 36 | 26/10 | 5 |
  | adam | 10K | 2 | 9 | 8/1 | 4 |

- **Tree 质量人工审查（10 篇）**
  - 优秀（7/10）：attention, gan, bitcoin, mapreduce, resnet, dropout, raft
    - 叙事弧完整（problem → mechanism → validation → conclusion）
    - Spine/branch 分配合理（branch = 例子、细节、对比）
    - Act 命名准确反映主题转换
  - 有问题（3/10）：
    - bert: 47 segs 偏多，SQuAD 细节过度切分
    - batchnorm: spine 26 vs branch 10，太多放 spine
    - adam: 只有 9 segs，算法核心机制描述缺失

- **Anchor 问题确认**
  - Anchor 是 segment 到原文的绑定机制（LLM 引用 8-15 字原文短语 → 字符串匹配定位）
  - 部分论文 anchor fail 率很高：bert 36/47、dropout 31/44、batchnorm 21/36
  - 根因：LLM 无法精确引用原文（轻微改写、省略词汇），字符串匹配容错不够
  - 计划重构：embedding-based semantic search + LLM 精选，替代字符串匹配

- **可视化 Demo（3 个版本迭代）**
  - `graph_demo.html`：D3 力导向图 — 用户反馈 "人类真的能使用吗？"
  - `tree_demo.html`：可折叠大纲 — 用户反馈 "我想要思维导图，不是大纲"
  - `mindmap_demo.html`：D3 水平树形思维导图 — 用户确认 "这种就很好了"

- **多文档提取框架**
  - `src/extraction/multi_doc_extractor.py`：跨文档关系提取（builds_on, contradicts, shares_mechanism）
  - Phase 3 初步跑通 transformer-evolution 和 distributed-systems 两组

- **Phase 2 问题发现**
  - econ-nash, sociology-granovetter, bio-crispr 三篇下载到的是登录/验证页面，不是论文 PDF（JSTOR/Science 付费墙）
  - blog-scaling 正常但 tree 失败（已修复）
  - 需要手动提供 PDF

### Decisions Made
- **从 entity-edge KG 转向 narrative-first 提取** — v8 pivot：segments（叙事单元）替代 entities，discourse relations 替代 typed edges
- **Adaptive chunking 替代 fixed chunking** — chunk count 对数缩放，避免长文档 segment 爆炸
- **Graph 保留为 ground truth，Tree 为 reading view** — graph 有全部 relations，tree 提供线性阅读路径
- **Tree structuring 用 LLM 而非算法** — 纯算法版本失败（全部 29 segments 上了 spine），因为 relation types 不够区分 spine vs branch
- **Anchor 需要 embedding-based 重构** — 字符串匹配对 LLM 引用的容错太低

- **Deep Dive: Adam 论文只产出 9 segments 的根因分析**
  - 现象：2 chunks，chunk 1 用了 7760 input + 4587 output tokens，但产出 **0 segments**。所有 9 segments 全来自 chunk 2
  - Chunk 1 内容：Abstract → Introduction → Algorithm 1 伪代码 → Bias Correction 推导 → Convergence Proof (Theorem 4.1) → Related Work → 实验开头 — **核心算法机制全在这里**
  - Chunk 2 内容：实验结果对比 + AdaMax 变体 + 结论 — 只有实验和延伸
  - **根因：PDF 解析 + 数学符号导致 JSON 生成失败**
    - 53 个 U+FFFD 替换字符（PDF 无法解析 hat notation：m̂ₜ → m�）
    - 22% 的行是数学公式（226 个 Unicode 特殊字符：β×62, θ×54, α×31, ∇, √, ∥ 等）
    - LLM 产出了 4587 tokens 的输出，但内容中嵌入的数学符号导致 JSON 格式损坏，`_parse_json` 返回空 dict
  - **修复（已实施）**：
    - Fix 1: `_preprocess_pdf_text()` — 在 chunking 前清理 U+FFFD、规范化 ligatures（ﬁ→fi）、清除控制字符
    - Fix 2: `_salvage_segments()` — 从 malformed JSON 中尝试提取 segments array，支持截断恢复
    - Fix 3: 0-segment chunk 自动重试一次，重试也失败则尝试 salvage retry 输出
    - Fix 4: 诊断日志 — 0-segment 时打印 raw output preview + 保存到 per_chunk results

- **Deep Dive: BERT 论文 47 segments 的根因**
  - 3 chunks，chunk 3 完全在 References 区域（References 从 char 37756 即 58% 处开始，chunk 3 从 char 45400 开始）
  - Chunk 3 仍产出了 13 segments — "skip non-teaching content" prompt 指导对 references 无效
  - 修复留待后续：考虑 chunking 前剥离 references，或加强 prompt

### Blockers / Issues
- Anchor fail 率在长论文上 50-70%，需要 embedding 方案重构
- BERT chunk 3 在 References 区域仍产出 segments — 需要 references 检测/剥离
- Phase 2 三篇论文需要手动 PDF

### Next
- [ ] 实现 embedding-based anchor resolution（句子 embedding → top-K 检索 → LLM 精选）
- [ ] 重跑 Phase 1 验证 PDF 预处理 + salvage 对 adam 的改善
- [ ] 加入 references 区域检测，chunking 前剥离
- [ ] 手动提供 Phase 2 PDF，跑 cross-discipline 评估

---

## 2026-02-21

### Completed

- **Narrative Extractor: Review Pass + Anchor Resolution**
  - 新增 LLM-based review pass (`review_narrative()` + `apply_review()`):
    - Segment 去重：检测因 chunk overlap 产生的重复 segments，保留质量更好的
    - Relation type 修正：统一到 preferred types（motivates, elaborates, exemplifies 等）
    - Concept label 归一化：合并不同名称的同一概念（如 "wait()" / "pthread_cond_wait"）
    - Chain merge resolution：A→B, B→C 自动解析为 A→C
    - 悬挂引用清理：merge 后自动删除指向已移除 segment 的 relations
  - 新增 `NARRATIVE_REVIEW_PROMPT`（`src/extraction/narrative_prompts.py`）
  - 新增 `src/binding/anchor_resolver.py` — 文本-图谱双向绑定:
    - 5 层匹配策略：exact → case-insensitive → normalized whitespace → prefix words → fallback
    - 按文档顺序约束匹配位置，避免乱序
    - `build_segment_ranges()` 根据 anchor 位置估算 segment 的文本跨度
  - 更新 chunk extraction prompt:
    - 新增 dedup 指导："Check Story so far, don't create duplicates"
    - 新增 anchor 字段："quote 8-15 words exactly from text"
    - 新增 skip non-teaching content 指导
  - `run_narrative.py` 新增 `--skip-review` 参数和 review/anchor 报告输出

- **Graph-to-Tree Structuring（Reading Tree）**
  - 新增 `src/transform/graph_to_tree.py` — LLM-based 图→树转换:
    - Spine 识别：LLM 判断哪些 segments 构成主叙事线（通常 40-60%）
    - Act 分组：将 spine 按主题转换分为 2-5 个 acts
    - Branch 挂接：非 spine segments 挂到最相关的 spine 节点下
    - See-also 链接：跨 act 的 back-references 保留为 see_also
    - Orphan 兜底：未被 LLM 安排的 segments 自动挂到最后一个 act
  - 新增 `NARRATIVE_TREE_PROMPT`（`src/extraction/narrative_prompts.py`）
  - `run_narrative.py` 新增 `--skip-tree` 参数和树形结构可视化输出
  - 设计原则：Graph 是 ground truth（全部 relations），Tree 是 reading view（线性+深度控制）

### Decisions Made
- Anchor resolution 使用纯字符串匹配（不需 LLM）— 快速、确定性、可调试
- Review pass 是可选的（`skip_review=True` 可跳过）— 便于 A/B 对比
- Open edge types 保留不变 — review 只修正到 preferred types，不强制
- Graph 和 Tree 是同一数据的两个视图 — graph 保留完整关系，tree 提供可读的层次结构
- Tree structuring 使用 LLM 而非纯算法 — spine vs branch 判断需要语义理解

### Next
- [ ] 运行 v9 narrative 实验，收集 review + anchor + tree 指标
- [ ] 评估 anchor 命中率，决定是否需要更强的 fuzzy matching
- [ ] 评估 tree spine 选择质量，对比 GT 的 core nodes
- [ ] 增加第二个 benchmark 文档验证泛化性

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

- **v7 Two-Pass 提取实验（ADR-0006 Tiered Model Strategy）**
  - 假设：用便宜模型（Flash Lite）提取实体，用更强模型（Flash）提取关系，可以改善边质量
  - Pass 1: Entity-only prompt + Flash Lite → 23 entities
  - Pass 2: Relation prompt (带 Pass 1 实体列表) + Flash → 30 relationships (0 dropped)
  - 创建 `src/extraction/two_pass_extractor.py`、`experiments/runners/run_two_pass.py`、`experiments/configs/v7_two_pass.yaml`
  - 新增 prompts: `ENTITY_ONLY_PROMPT`（Pass 1）、`RELATION_PROMPT_TEMPLATE`（Pass 2，含方向指导）

- **v7 实验结果（threads-cv）**

| 指标 | v6 整文档 | **v7 Two-Pass** | 变化 | 目标 |
|---|---|---|---|---|
| 实体数 | 20 | **23** | +3 | ~17 |
| 核心节点召回 | 87.5% (7/8) | **87.5% (7/8)** | 持平 | >60% |
| 全部节点召回 | 70.6% (12/17) | **70.6% (12/17)** | 持平 | — |
| 核心边召回 | 37.5% (3/8) | **37.5% (3/8)** | 持平 | >60% |
| 全部边召回 | 26.7% (4/15) | **20.0% (3/15)** | -1 条 | — |
| 提取边数 | 19 | **30** | +11 | — |
| Input tokens | 11,504 | **23,634** | +2.1x | — |
| Output tokens | 2,481 | **12,379** | +5x | — |

- **v7 根因分析 — 更多边但更低召回**
  - **过度生成 Supports 边**：6 条研究者归因边（Dijkstra→CV, Hoare→CV, Lampson&Redell→Mesa 等），GT 显式排除了这类边
  - **实体命名不匹配**：提取 "Lock" 但 GT 期望 "Lock/Mutex"，evaluator substring matching 匹配失败
  - **核心实体缺失级联**："Use While Loop Rule" 未提取 → 阻断 Mesa→WhileLoopRule [Causes] 核心边
  - **关系方向反转**：Lock→CV [Enables] vs GT 的 CV→Lock [Enables]
  - **关系类型混淆**：IsA vs PartOf 混用（Bounded Buffer / Producer-Consumer）
  - **Causes 类型边几乎完全缺失**：Producer→Buffer、Consumer→Buffer 均未识别
  - 匹配的 3 条边：wait()→CV [PartOf], signal()→CV [PartOf], Mesa→CV [HasProperty]
  - **结论**：瓶颈不在模型能力，而在 (1) Pass 1 实体集质量级联 (2) Supports 类型过度生成 (3) evaluator 匹配逻辑过严

### Decisions Made
- **Abandon embedding cosine similarity for ER** — 无法在 under-merge 和 over-merge 之间找到平衡点（ADR-0004 → Superseded）
- **Adopt Graphiti-style cascading ER** — 确定性优先、LLM 兜底的三层方法 (ADR-0005)
- **Chunk size 从 512 chars 提升至 6000 chars** — 根因是 `length_function=len` 按字符计数，128 tokens 太碎导致实体爆炸
- Chunk size 是比 ER 更大的杠杆：源头减少碎片 > 下游修补重复
- **Repo 重构为 config-driven experiment organization** (ADR-0007) — src/ 只保留活跃代码，实验通过 YAML config 驱动
- **整文档提取可行但边质量受限** — 实体质量已达标（20 entities, 87.5% core recall），但边的方向和类型判断是 Flash Lite 模型能力瓶颈

### Blockers / Issues
- 边召回仍未达标（37.5% core vs 目标 >60%）— v7 two-pass 证明更强模型不是银弹
- Eval 子串匹配过于严格 — "Wait Must Re-check Condition" vs "Use While Loop Rule" 无法匹配，"Lock" vs "Lock/Mutex" 也无法匹配
- 模型过度生成 Supports 研究者归因边（6/30 = 20% 的提取边是噪声）

### Next
- [ ] 增强 eval 匹配逻辑（模糊匹配 / synonym 映射 / 双向边匹配），减少假阴性
- [ ] 边方向归一化：PartOf 等方向敏感的边类型考虑双向匹配或规范化
- [ ] Prompt 约束 Supports 类型：明确禁止研究者归因边，或在后处理中过滤
- [ ] 实体集质量提升：确保 "Use While Loop Rule" 等核心实体被提取
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
