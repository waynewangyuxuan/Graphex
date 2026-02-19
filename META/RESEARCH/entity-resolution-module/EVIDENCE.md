# Evidence: Embedding-Based Entity Resolution

## 对标项目

### iText2KG (AuvaLab/itext2kg)
- **GitHub**: https://github.com/AuvaLab/itext2kg
- **Stars**: 1.2k+, MIT-like license
- **论文**: https://arxiv.org/html/2409.03284v1
- **核心贡献**: 证明 embedding cosine similarity 可以完全替代 LLM-based entity resolution

### 关键源码位置

#### Entity 模型（带 embedding 的 Pydantic model）
- `itext2kg/atom/models/entity.py:25-49`
- Entity 有 name, label, properties.embeddings
- `__eq__` 基于 (name, label) 精确匹配
- `process()` 做标准化：lowercase, 去除特殊字符

#### Embedding 计算（加权 name + label）
- `itext2kg/atom/models/knowledge_graph.py` → `embed_entities()`
- `text = w_name * embed(name) + w_label * embed(label)`
- 默认权重：entity_name_weight=0.8, entity_label_weight=0.2

#### 核心匹配算法（batch cosine similarity）
- `itext2kg/atom/graph_matching/matcher.py:19-102`
- `_batch_match_entities()` 流程：
  1. 精确匹配 pass（name+label 完全相等）
  2. 剩余实体构建 embedding 矩阵 `np.vstack([e.properties.embeddings])`
  3. `cosine_similarity(e1_embs, e2_embs)` → sim_matrix (N, M)
  4. `sim_matrix.argmax(axis=1)` + threshold 过滤
  5. 超过阈值 → 合并为同一实体

#### 并行归约合并
- `itext2kg/atom/atom.py:55-84`
- `parallel_atomic_merge()` 实现二叉树归约：
  - while len(current) > 1: 配对 → ThreadPoolExecutor → merge_two_kgs
  - 奇数个 KG 时最后一个 leftover 下一轮合并

#### Relationship 引用更新
- `itext2kg/atom/graph_matching/matcher.py:176-233`
- `match_entities_and_update_relationships()`:
  1. 匹配实体 → 得到 entity_name_mapping
  2. 遍历所有 relationship，将 startEntity/endEntity 重映射到合并后的实体
  3. 合并 relationships 列表

### 其他参考

#### graphrag-psql (jimysancho/graphrag-psql)
- 在 nano-graphrag/LightRAG 基础上加了 fuzzywuzzy 的 entity merging
- 更简单，但只做字符串模糊匹配，没有 embedding

#### Neo4j + LangChain 方案
- k-NN embedding graph → weakly connected components → LLM 判断合并
- 更复杂，适合 production scale（百万级实体）

#### 行业共识 (2025-2026)
- Cascading matcher: Rules → ML/Embedding → LLM（成本递增，频次递减）
- Embedding-based blocking 已替代传统 LSH 成为主流
- Microsoft GraphRAG 自身未实现 entity resolution（承认这是缺失）
