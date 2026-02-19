# Integration Guide: Embedding-Based Entity Resolution for Graphex

## 影响面

### 新增文件
- `src/resolution/entity_resolver.py` — 三层级联匹配器
- `src/resolution/parallel_merge.py` — 二叉归约合并器

### 修改文件
- `benchmark/scripts/cocoindex_spike.py` — 替换 `merge_chunk_results()` 为新方案
- `requirements.txt` — 新增 sentence-transformers, scikit-learn

### 不受影响
- 提取层（cocoindex_spike 的 `extract_chunk_cocoindex_style()`）不变
- 评估层（`evaluate_against_ground_truth()`）不变
- Ground Truth 和 benchmark 数据集不变

## 依赖

```
sentence-transformers>=2.2.0    # embedding 计算
scikit-learn>=1.0                # cosine_similarity
numpy>=1.21                      # 矩阵运算
```

可选：
```
litellm                          # LLM 兜底层（已有）
```

## 实现步骤

### Step 1: EntityResolver 类（核心）

```python
class EntityResolver:
    def __init__(self, model_name="all-MiniLM-L6-v2", threshold=0.8):
        self.model = SentenceTransformer(model_name)
        self.threshold = threshold

    def embed_entities(self, entities: list[dict]) -> np.ndarray:
        texts = [f"{e['label']}: {e.get('definition', '')}" for e in entities]
        return self.model.encode(texts)

    def resolve(self, entities: list[dict]) -> tuple[list[dict], dict]:
        """返回 (去重后的实体列表, id_remap: old_id → canonical_id)"""
        embeddings = self.embed_entities(entities)
        sim_matrix = cosine_similarity(embeddings)
        # Union-Find 或 greedy clustering
        ...
```

### Step 2: Parallel Merge（从 iText2KG 学来的模式）

```python
def parallel_merge(chunk_kgs: list[dict], resolver: EntityResolver, max_workers=4):
    current = chunk_kgs
    while len(current) > 1:
        pairs = [(current[i], current[i+1]) for i in range(0, len(current)-1, 2)]
        leftover = current[-1] if len(current) % 2 else None
        with ThreadPoolExecutor(max_workers) as ex:
            merged = list(ex.map(lambda p: merge_two_kgs(p[0], p[1], resolver), pairs))
        if leftover: merged.append(leftover)
        current = merged
    return current[0]
```

### Step 3: LLM 兜底（可选，Phase 2）

```python
def llm_resolve_ambiguous(pairs: list[tuple], model="gemini/gemini-2.0-flash"):
    """对灰区 pair (similarity 0.6-0.8) 调用 LLM 判断"""
    prompt = f"Are these two entities referring to the same concept?\n"
    prompt += f"Entity A: {pair[0]['label']} - {pair[0]['definition']}\n"
    prompt += f"Entity B: {pair[1]['label']} - {pair[1]['definition']}\n"
    prompt += "Answer YES or NO with brief reason."
    ...
```

## 冲突与风险

### 与现有 Entity Resolution 模块的关系
- 现有 `src/pipeline/enhanced_pipeline.py` 里有 `known_entities` 传参机制
- 新方案**替代**这个机制（后处理 vs 前置传参），但可以共存
- 如果保留两者，可以把 `known_entities` 作为全局 anchor 列表，新方案在此基础上做跨 chunk 合并

### 性能考量
- `all-MiniLM-L6-v2` 编码 113 个 entity ≈ 50ms（CPU）
- cosine_similarity 矩阵 113×113 ≈ <1ms
- 主要瓶颈在 embedding 模型首次加载（~2s），但只需加载一次
- 整个 entity resolution 过程应该 < 1s（排除 LLM 兜底）

### 过度合并风险
- 阈值太低会合并不该合并的实体（如 "Lock" 和 "Lock-free"）
- 缓解：同时考虑 entity type 是否一致；加入 definition embedding 提高区分度
- 验证：跑 benchmark 时同时看 precision（不该合并的没被合并）

## 验证清单

- [ ] `EntityResolver` 能把 "Lock" / "Mutex" / "Mutex Lock" 合并为一个实体
- [ ] "Producer Thread" / "Producer" / "Producer/Consumer" 正确处理（Producer Thread→Producer 合并，Producer/Consumer 保持独立）
- [ ] "Python: Language" vs "Python: Snake" 不会被合并（不同 type/definition）
- [ ] threads-cv benchmark: 113 entities → ~20-25 entities，核心节点召回保持 100%
- [ ] 核心边召回 ≥ 60%（因为实体合并后边的 source/target 对齐了）
- [ ] 性能：entity resolution 总耗时 < 2s
