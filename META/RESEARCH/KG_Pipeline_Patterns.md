# KG 提取 Pipeline 模式

> **来源**：GraphRAG (Microsoft) + nano-graphrag 实现模式提炼
>
> **知识来源**：Prism output/kg-extraction-pipeline（应用于 2026-02-18）
>
> **应用优先级**：P0（立即）→ P1（下阶段）→ P2（生产优化）

---

## P0：立即集成

### Gleaning — 迭代提取提升召回率

**问题背景**：EXP-001 显示核心节点召回仅 37.5%。单次 LLM 提取在密集文本中会系统性遗漏实体。

**方案**：在 Phase 2 (Guided Extraction) 内部嵌入追问轮：

```
Round 1: 正常提取 → 初始实体集
Round 2+: "可能有遗漏的实体，请继续提取" → 追加实体
终止: LLM 回答"无更多"或达到 max_gleanings 上限
```

**参数设计**：

- `max_gleanings`：可调，建议从 1 开始；每增加 1 轮约 2x token 消耗，召回提升递减
- 仅对长 chunk (>500 tokens) 启用；短 chunk 信息密度低，gleaning 价值不大

**预期效果**：基于 GraphRAG 实践，1 轮 Gleaning 提升 10-20% 召回率。结合 First-Pass 引导，核心节点召回预期从 ~37% 升至 55-65%。

---

### Phase 4: Entity Resolution — 实体合并与去重

**问题背景**：跨 chunk 提取产生重复实体；现有 EntityRegistry 仅做精确名称匹配，无描述合并。

**Graphex 已有基础**：
- `EntityRegistry`：精确匹配 + embedding 相似度，防止 intra-run 重复
- Node schema 中有 `aliases` 字段

**P0 策略 — 类型感知描述聚合**：

```
merge_entity(existing, new_entity):
  match_keys = [label.lower()] + [a.lower() for a in aliases]
  if match_keys 有交集 且 类型兼容:
    if type_conflict:
      existing.type = most_frequent_type([existing.type, new_entity.type])
    existing.descriptions.append(new_entity.description)
    if token_count(descriptions) > THRESHOLD:
      existing.definition = llm_summarize(descriptions)  # 可用 cheap model
    existing.aliases = union(existing.aliases, new_entity.aliases)
    existing.sources.append(new_entity.source)
```

**Enhancement（配合 Technical.md §4.4）**：embedding 聚类处理词法无法捕获的同义词（"CV" vs "Condition Variable"），在描述聚合之后运行。

**边的合并**（与实体合并同步）：

- 权重累加：`merged_weight = sum(edge.weight for same entity pair)`
- 方向归一化：`key = tuple(sorted([src_id, tgt_id]))` — 确保 (A→B) 与 (B→A) 归为同一条边

**接入点**：Grounding Verification (Phase 3) **之后**，作为 Phase 4 运行。

---

## P1：下阶段规划

### 社区检测 — Progressive Disclosure 支撑

**算法**：Leiden（Louvain 改进版，保证社区内连通性）。Python 包：`graspologic`。

**层级结构**：

```
Level 0: 全图 → 课程/文集视图
Level 1: 3-8 个大社区 → 主题区域
Level 2: 每大社区内 2-5 个子社区 → 概念群
叶节点: 单个实体
```

**参数**：`max_cluster_size = 10`（与 Miller's Law 对齐，单屏可展示 5-7 个核心节点）

**接入点**：Entity Resolution (Phase 4) 之后，输出之前（Phase 5）。

---

### 存储抽象 — upsert 语义

**核心语义**：`upsert`（同一 ID 第二次调用时**合并**而非覆盖），使多 chunk、多文档的实体合并成为存储层天然行为。

**最小接口**：

```
upsertNode(id, props), upsertEdge(src, tgt, props)
getNode(id), getNeighbors(id, edgeType?)
hasNode(id), nodeDegree(id)
```

**MVP 实现**：NetworkX（内存图）。升级路径：接口不变，替换为 Neo4j。

---

## P2：生产优化

| Pattern | 描述 |
|---------|------|
| 社区报告 | 每个社区用 cheap model 生成 2-4 句摘要，作为"主题标题 + 简介" |
| 异步并发 | Semaphore 限制并发 LLM 调用（建议 4-8 路），避免 rate limiting |

---

## 不采纳的 Pattern

| Pattern | 原因 |
|---------|------|
| 分隔符输出格式 (`<\|>`) | Graphex 有 typed schema，JSON 更结构化；分隔符适合无 schema 场景 |
| 词法去重（仅按名称分组） | 太粗糙；Graphex 有 `aliases` 字段，应使用别名感知合并 |
| 无类型自由关系 | Graphex 已有 10 种边类型，不退化为描述性文本 |

---

## P0 完成验证清单

- [ ] Entity Resolution 后重复实体降至 0
- [ ] Gleaning 后核心节点召回 >60%（benchmark: threads-cv 文档）
- [ ] 健康指标仍在推荐范围（压缩率 200-350，密度 1.2-1.8）
- [ ] 多 chunk 场景下同一实体的描述被正确合并

*证据来源：GraphRAG v1.x 源码、nano-graphrag 主分支，2026-02 审阅。详见 Prism output/kg-extraction-pipeline/EVIDENCE.md。*
