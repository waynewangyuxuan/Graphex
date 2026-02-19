# Embedding-Based Entity Resolution for Knowledge Graphs

## Pattern Summary

**问题**：从多个 chunk 并行提取的 KG 实体存在大量重复（同一概念不同表述），需要合并。

**核心 Pattern**：三层级联匹配 + 并行归约合并。

---

## 1. 三层级联匹配（Cascading Matcher）

按成本从低到高依次尝试：

### Layer 1: 精确匹配（Zero-cost）
- 标准化后的 `(name, label)` 完全相等 → 直接合并
- 标准化规则：lowercase, 去除 `_`, `"`, `-`, 特殊字符替换

### Layer 2: Embedding Cosine Similarity（主力）
- 对每个实体计算 embedding：`embed(name) * w_name + embed(label) * w_label`
  - 默认权重：name=0.8, label=0.2（iText2KG）
  - 作用：避免合并 name 相似但 type 不同的实体（如 "Python: Language" vs "Python: Snake"）
- 构建相似度矩阵：`cosine_similarity(batch_emb_1, batch_emb_2)` → (N, M) matrix
- 阈值 θ_E = 0.8（实体），θ_R = 0.7（关系）
- 每个实体取最高相似度的匹配，超过阈值即合并

### Layer 3: LLM 兜底（高成本，低频次）
- 对 Layer 2 中 **置信度在灰区**（如 0.6-0.8）的候选对，调用 LLM 判断是否合并
- Prompt 示例：给出两个实体的 name + definition，问"这两个是否指同一概念？"
- 仅处理少量 ambiguous cases，控制 LLM 调用次数

---

## 2. 并行归约合并（Parallel Pairwise Merge）

解决"N 个 chunk 的 KG 如何高效合并"：

```
[KG1, KG2, KG3, KG4, KG5, KG6, KG7, KG8]
          ↓ parallel merge pairs
[KG12,   KG34,   KG56,   KG78]
          ↓ parallel merge pairs
[KG1234,         KG5678]
          ↓ merge
[KG_final]
```

- **时间复杂度**：O(log N) 轮（vs 顺序 O(N)）
- **每轮并行**：ThreadPoolExecutor, max_workers=4-8
- **每次 merge** = match_entities → update_relationship_references → deduplicate

关键步骤：
1. 匹配 KG_a.entities vs KG_b.entities → 得到 entity_mapping
2. 将 KG_a 的所有 relationship 中的 entity 引用重映射到合并后的 entity
3. 合并后的 KG = deduplicated_entities + remapped_relationships

---

## 3. 实体 Embedding 策略

### 推荐模型
- **轻量**：`all-MiniLM-L6-v2`（384 维，速度快，质量够用）
- **中等**：`text-embedding-3-small`（OpenAI, 1536 维）
- **无需 GPU**：以上均可 CPU 运行，数百实体 <1s

### Embedding 输入构造
```python
text = f"{entity.name}: {entity.label}"
# 或加权：
emb = w_name * embed(name) + w_label * embed(label)
```

加入 definition 可提高语义区分度，但增加 token 消耗。

---

## 4. 关键设计决策

### 为什么不用 LLM 做主力匹配？
- **延迟**：100 个实体 pair 需 100 次 LLM 调用 → 太慢
- **不可并行**：API rate limit 限制
- **成本**：embedding 是一次性计算，cosine similarity 是纯数学运算
- iText2KG 重构时就是把 LLM-based resolution 替换成 cosine similarity → 速度提升 10x+

### 阈值怎么定？
- iText2KG 用 1500 个 entity pair + 500 个 relation pair 做标定
- 建议：从 0.8 开始，跑 benchmark 微调
- 灰区 [0.6, 0.8) 的 pair 是 LLM 兜底的目标

### 合并时保留哪个实体的信息？
- **名字**：保留较长/更完整的那个（"Condition Variable" > "CV"）
- **定义**：保留更详细的，或拼接
- **类型**：如果冲突，优先保留来自更多 chunk 的那个（投票机制）

---

## 5. 工作流集成

```
PDF → Chunk → [并行提取 N 个 mini-KG] → [计算 entity embeddings]
    → [Parallel Pairwise Merge (embedding matching)]
    → [LLM 兜底灰区 pairs]
    → Final KG
```

与 Graphex 现有架构的映射：
- `cocoindex_spike.py` 的 `extract_chunk_cocoindex_style()` → 产出 N 个 mini-KG（可并行）
- 新增 `EntityResolver` 类 → 实现三层级联匹配
- 新增 `parallel_merge()` → 实现二叉归约
- 现有 `merge_chunk_results()` → 替换为上述方案
