# 学术研究调研：LLM 知识图谱抽取

> **目的**：调研与 Graphex Pipeline 相关的学术领域，将成功经验应用到我们的场景
>
> **日期**：2026-02-12
>
> **相关问题**：Entity 噪声过滤、Relation 类型分类、技术文档适配

---

## 1. 相关学术领域

| 领域 | 与我们的关联 | 关键挑战 |
|------|-------------|---------|
| **Knowledge Graph Construction (KGC)** | 核心任务 | 从非结构化文本抽取结构化知识 |
| **Named Entity Recognition (NER)** | Entity Extraction | 识别实体边界和类型 |
| **Relation Extraction (RE)** | Edge Extraction | 关系分类、避免泛化 |
| **Prompt Engineering** | LLM 控制 | 输出稳定性、格式合规 |
| **Schema-Guided Extraction** | 约束抽取 | 按预定义 schema 抽取 |
| **Few-Shot Learning** | 低资源场景 | 少量样本学习 |

---

## 2. 关键研究发现

### 2.1 Prompt 策略比较

根据 [Testing prompt engineering methods for knowledge extraction](https://journals.sagepub.com/doi/10.3233/SW-243719) 的实验：

| 策略 | 效果 | 适用场景 |
|------|------|---------|
| **Zero-Shot (ZSP)** | 基线 | 简单任务、schema 清晰 |
| **Few-Shot (FSP)** | ✅ 显著提升 | 复杂任务、需要示例锚定 |
| **Chain-of-Thought** | ⚠️ 不如预期 | 推理任务，但对抽取帮助有限 |
| **Self-Consistency** | ✅ 有效 | 降低噪声、提高一致性 |
| **Generated Knowledge** | ⚠️ 风险高 | 需要领域背景时使用 |

> **关键发现**：CoT 对知识抽取效果不显著，Few-Shot 配合检索选择示例效果最好。

### 2.2 Schema-Guided 抽取框架

根据 [PARSE: LLM Driven Schema Optimization](https://arxiv.org/html/2510.08623v1)：

**三阶段验证 (SCOPE)**：
1. **Missing Attribute Check** - 检查必填字段
2. **Grounding Verification** - 验证抽取值在原文中存在
3. **Rule Compliance Check** - 验证值符合 schema 约束

> **应用到我们的场景**：可以在后处理阶段添加 Grounding Verification，检查抽取的实体是否真的在原文中出现。

### 2.3 关系抽取最新进展

根据 [A survey on cutting-edge relation extraction techniques](https://link.springer.com/article/10.1007/s10462-025-11280-0)：

**DSARE 框架**：
- 使用训练样本的结构信息（文本、关系标签、头尾实体类型）作为 prompt
- 用 KNN 检索与当前实例相关的样本辅助预测

**文档级关系抽取**：
- Graph-based：将文档构建为图，词作为节点，语言关系作为边
- Transformer-based：利用长上下文理解

> **应用到我们的场景**：可以添加 Few-Shot 示例检索，针对不同文档类型检索相关示例。

### 2.4 Few-Shot 关系抽取

根据 [Few-Shot Relation Extraction Based on Prompt Learning](https://dl.acm.org/doi/10.1145/3746281)：

**模板构建策略**：
| 策略 | 优点 | 缺点 |
|------|------|------|
| 手动构建 | 可控性强 | 效率低、泛化差 |
| 自动构建 | 无需人工 | 可能生成无效模板 |
| 混合策略 | 平衡 | ✅ 推荐 |

**实体类型提示**：在 prompt 中加入实体类型信息显著提高关系分类准确性。

> **应用到我们的场景**：在 Relation Extractor 的 prompt 中，明确给出 source/target 实体的类型，帮助判断关系类型。

### 2.5 Self-Consistency Prompting

根据 [Semantic Web Journal](https://www.semantic-web-journal.net/system/files/swj3606.pdf)：

```
First, think about entities and relations that you want to extract from the text.
Then, look at the potential triples.
Think like a domain expert and check the validity of the triples.
Filter out the invalid triples.
Return the valid triples in JSON format.
```

> **应用到我们的场景**：在 prompt 末尾添加"作为领域专家检查"的指令。

---

## 3. 与我们问题的映射

### 问题 1: Entity 噪声过滤 (文件名、作者名)

**学术解决方案**：
1. **Schema 约束** - 明确定义什么是有效实体
2. **Grounding Verification** - 检查实体是否在核心内容中出现
3. **负面示例** - Few-Shot 中加入"不应该抽取"的例子

**具体改进**：
```python
# 添加负面示例到 prompt
"""
## ❌ 不应该抽取的例子

以下是一些不应被抽取为实体的例子：
- "main-two-cvs-if.c" - 这是文件名，不是概念
- "ARPACI-DUSSEAU" - 这是版权作者，不是对内容有贡献的人
- "B.W. Lampson" - 这是参考文献作者
"""
```

### 问题 2: RelatedTo 过度使用 → **已通过移除 RelatedTo 解决**

**最终方案（2026-02-12）**：
直接移除 RelatedTo 边类型。原因：
- RelatedTo 太泛化了，两个有边的节点必然是"相关的"
- 这种 fallback 导致了懒惰分类（测试中 76% 使用 RelatedTo）
- 新策略：如果无法确定具体关系类型，**不创建边**

**辅助改进**：
1. **实体类型引导** - 告诉 LLM 两个实体的类型，缩小关系选择范围
2. **Few-Shot 示例** - 每种边类型给 1-2 个真实例子
3. **强制推理** - 要求解释为什么选择该关系类型

**具体改进**：
```python
# 添加实体类型引导
"""
## Entities to Connect

- **entity_001** [Concept]: Condition Variable
  Definition: A synchronization primitive...

- **entity_002** [Method]: wait()
  Definition: An operation that puts thread to sleep...

Given that entity_001 is a Concept and entity_002 is a Method,
consider these likely relations:
- PartOf: If the Method is part of the Concept's API
- Enables: If the Concept enables the Method's functionality
- HasProperty: If the Method is a property/feature of the Concept

⚠️ If NONE of these fit, do NOT create an edge!
"""
```

### 问题 3: 核心概念召回率低

**学术解决方案**：
1. **两阶段抽取** - 先全局扫描识别主题，再逐 chunk 抽取
2. **标题/摘要优先** - 从标题和摘要中提取核心概念作为 seed
3. **Decomposed Prompting** - 分解为多个子任务

**具体改进**：
```
Stage 1: Document Understanding
- 识别文档类型（教科书、论文、文档）
- 提取章节标题中的核心概念
- 生成 5-10 个必须抽取的关键概念

Stage 2: Chunk-level Extraction
- 在每个 chunk 的 prompt 中注入核心概念列表
- 要求检查这些概念是否在当前 chunk 中出现
```

---

## 4. 推荐改进优先级

| 优先级 | 改进项 | 来源 | 预期效果 | 状态 |
|--------|--------|------|---------|------|
| **P0** | ~~移除 RelatedTo 边类型~~ | 内部决策 | 强制精确分类 | ✅ 已完成 |
| **P0** | 添加 Few-Shot 负面示例 | [Prompt Engineering Guide](https://www.promptingguide.ai/prompts/information-extraction) | 噪声 -50% | 待实施 |
| **P0** | 实体类型引导关系选择 | [RE Survey](https://link.springer.com/article/10.1007/s10462-025-11280-0) | 精确度 +30% | 待实施 |
| **P1** | Self-Consistency 验证 | [Semantic Web](https://www.semantic-web-journal.net/system/files/swj3606.pdf) | 精度 +15% | 待实施 |
| **P1** | 两阶段抽取 (先全局后局部) | [LLM-KG Survey](https://arxiv.org/html/2510.20345v1) | 召回 +20% | 待实施 |
| **P2** | Grounding Verification | [PARSE](https://arxiv.org/html/2510.08623v1) | 噪声 -30% | 待实施 |
| **P2** | 动态 Few-Shot 示例检索 | [DSARE](https://link.springer.com/chapter/10.1007/978-981-97-5569-1_22) | 泛化能力 +20% | 待实施 |

---

## 5. 实验设计建议

### EXP-004: 添加 Few-Shot 负面示例

**假设**：添加"不应抽取"的负面示例会减少噪声实体

**修改**：在 Entity Extractor prompt 中添加负面示例

**测量**：噪声实体率变化

### EXP-005: 实体类型引导关系选择

**假设**：告知实体类型会帮助 LLM 选择更精确的关系类型

**修改**：在 Relation Extractor prompt 中添加类型引导提示

**测量**：RelatedTo 占比变化、精确关系类型使用率

### EXP-006: 两阶段抽取

**假设**：先识别核心概念再逐 chunk 抽取会提高召回率

**修改**：添加 First-Pass Agent 识别文档主题和核心概念

**测量**：核心节点召回率变化

---

## 6. 参考文献

1. [LLM-empowered knowledge graph construction: A survey](https://arxiv.org/html/2510.20345v1) - 2024
2. [Testing prompt engineering methods for knowledge extraction from text](https://journals.sagepub.com/doi/10.3233/SW-243719) - 2025
3. [A survey on cutting-edge relation extraction techniques based on language models](https://link.springer.com/article/10.1007/s10462-025-11280-0) - 2025
4. [Few-Shot Relation Extraction Based on Prompt Learning](https://dl.acm.org/doi/10.1145/3746281) - 2024
5. [PARSE: LLM Driven Schema Optimization for Reliable Entity Extraction](https://arxiv.org/html/2510.08623v1) - 2025
6. [Information Extraction with LLMs - Prompt Engineering Guide](https://www.promptingguide.ai/prompts/information-extraction)
7. [Structured Entity Extraction Using Large Language Models](https://arxiv.org/html/2402.04437v3) - 2024

---

*本文档将随研究进展持续更新*
