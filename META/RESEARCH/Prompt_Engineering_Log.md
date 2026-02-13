# Prompt Engineering 观察与改进日志

> **目的**：系统性追踪 AI 提取 Pipeline 的 Prompt 优化过程
>
> **更新规则**：每次实验后添加新条目，记录问题、假设、修改、结果

---

## 实验索引

| 日期 | 实验编号 | 目标 | 核心节点匹配率 | 状态 |
|------|---------|------|---------------|------|
| 2026-02-12 | EXP-001 | Baseline 评估 | 37.5% | ✅ 完成 |
| - | EXP-002 | Entity Prompt 优化 | 目标 >70% | 🔜 待做 |
| - | EXP-003 | Relation Prompt 优化 | 目标 RelatedTo <40% | 🔜 待做 |

---

## EXP-001: Baseline 评估

**日期**: 2026-02-12

**目标**: 建立基准指标，识别主要问题

### 测试文档
- threads-cv.pdf (OSTEP Chapter 30: Condition Variables)

### 当前 Prompt 配置

**Entity Extractor System Prompt (v0.1)**:
```
You are an expert Entity Extraction Agent for knowledge graph construction.

Your task is to extract all entities from the given text according to the schema.

## Entity Types
- Concept: Abstract concepts or categories
- Event: Things that happen with start/end time
- Agent: Conscious actors - people, organizations
- Claim: Propositions that can be true/false
- Fact: Verified factual statements

## Guidelines
1. Extract ONLY entity types defined above
2. Use exact text spans from the source when possible
3. Assign confidence scores (0.0-1.0) based on how clearly the entity is defined
4. Each entity needs a clear label (2-10 words) and definition (1-3 sentences)
5. If an entity matches a known entity, note it in your response
```

**Relation Extractor System Prompt (v0.1)**:
```
You are an expert Relation Extraction Agent for knowledge graph construction.

## Relation Types
- IsA: Type attribution
- PartOf: Part-whole relation
- Causes: Causation
- Before: Temporal ordering
- HasProperty: Attribute
- Supports: Evidence supports claim
- Attacks: Contradicts or refutes
- RelatedTo: Generic association (use only when no specific relation applies)

## Guidelines
1. Only create relations between entities in the provided list
2. Use the source text to justify each relation
3. Assign confidence based on how explicit the relation is in the text
4. Prefer specific relation types over RelatedTo
5. Include the evidence text span for each relation
```

### 测量结果

| 指标 | 数值 | 评价 |
|-----|------|------|
| 核心节点召回率 | 3/8 = **37.5%** | ❌ 差 |
| 核心边召回率 | 2/8 = **25%** | ❌ 差 |
| 噪声节点率 | 10/19 = **52.6%** | ❌ 严重 |
| RelatedTo 占比 | 13/17 = **76.5%** | ❌ 严重 |
| 重复实体数 | 4 | ❌ 差 |

### 观察到的问题

#### 问题 1: 噪声实体提取
**现象**:
- 提取文件名: `main-two-cvs-if.c`, `main-two-cvs-while.c`
- 提取 Copyright 作者: `ARPACI-DUSSEAU` (x2)
- 提取引用作者: `B.W. Lampson`, `D.R. Redell`
- 提取无关概念: `Linux man page`, `shared resource`

**假设原因**:
- Prompt 没有明确的噪声过滤规则
- LLM 在"extract all entities"指令下过于激进

#### 问题 2: 核心概念缺失
**缺失的核心概念**:
- `wait()` - 条件变量的核心操作
- `signal()` - 条件变量的核心操作
- `Lock/Mutex` - 必需的同步原语
- `Producer/Consumer Problem` - 章节主要应用场景
- `Bounded Buffer` - 核心数据结构

**假设原因**:
- 没有 `Method` 类型来表示操作/函数
- 没有告诉 LLM 什么是"核心"概念
- 逐 chunk 处理，可能在代码示例 chunk 中缺失概念定义

#### 问题 3: 边类型坍塌
**现象**: 76% 的边都是 `RelatedTo`

**实际需要的边类型分布**:
- PartOf: 4
- Enables: 3
- Contrasts: 2
- HasProperty: 2
- Causes: 1
- RelatedTo: 5

**假设原因**:
- Prompt 虽然说"prefer specific types"但没有给出选择指南
- 没有给出什么情况用什么类型的示例
- LLM 在不确定时默认使用 RelatedTo

#### 问题 4: 重复实体
**重复实体**:
- `CONDITION VARIABLES` vs `condition variables`
- `buffer` x 2 (不同定义)
- `ARPACI-DUSSEAU` x 2

**假设原因**:
- Entity Registry 的简单去重不够
- 不同 chunk 产生的相同概念没有被合并

### 结论与下一步

**优先级排序**:

| 优先级 | 改进项 | 预期效果 | 复杂度 |
|--------|--------|---------|--------|
| P0 | 添加噪声过滤规则到 Entity Prompt | 噪声 -80% | 低 |
| P0 | 添加 Method 类型 | 召回 +20% | 低 |
| P0 | 添加边类型选择指南 | RelatedTo <40% | 低 |
| P1 | 添加重要性标注 | 支持分层 | 中 |
| P1 | 添加全局文档理解 Pass | 召回 +15% | 中 |
| P2 | 升级去重算法 | 重复 -90% | 中 |

---

## EXP-002: Entity Prompt v0.2 (待执行)

**目标**:
- 噪声节点率 <15%
- 核心节点召回率 >70%

**计划修改**:

```python
SYSTEM_PROMPT_V02 = """You are an expert Entity Extraction Agent for knowledge graph construction.

## Entity Types (按重要性排序)

1. **Concept**: 抽象概念、理论、数据结构
   - 例: "Condition Variable", "Bounded Buffer", "Mesa Semantics"

2. **Method**: 操作、函数、API、算法步骤
   - 例: "wait()", "signal()", "pthread_cond_wait"

3. **Process**: 持续的活动或流程
   - 例: "Producer-Consumer synchronization"

4. **Agent**: 对内容有实质贡献的人物或组织
   - 例: "Dijkstra" (发明者), "Hoare" (理论提出者)
   - ⚠️ 不包括: 作者、引用文献作者

5. **Proposition**: 最佳实践、规则、观点
   - 例: "Always use while loops with condition variables"

## ⚠️ 噪声过滤规则 (重要!)

DO NOT extract as entities:
- [ ] 文件名 (*.c, *.py, *.java, *.txt)
- [ ] Copyright 声明中的作者名
- [ ] 参考文献中的作者名
- [ ] 代码变量名 (除非代表概念)
- [ ] 页码、章节号、图表编号
- [ ] 过于泛化的词 ("thing", "stuff", "resource")

## 重要性标注

为每个实体标注 importance 级别:
- **core**: 章节标题提到 / 有专门段落解释 / 在总结中强调
- **supporting**: 帮助理解核心概念的辅助概念
- **peripheral**: 提及但非重点的背景信息

## Output Format
{
  "entities": [
    {
      "id": "entity_001",
      "type": "Method",
      "label": "wait()",
      "definition": "Operation that puts the calling thread to sleep...",
      "importance": "core",
      "confidence": 0.95
    }
  ]
}
"""
```

---

## EXP-003: Relation Prompt v0.2 (待执行)

**目标**:
- RelatedTo 占比 <40%
- 核心边召回率 >60%

**计划修改**:

```python
SYSTEM_PROMPT_V02 = """You are an expert Relation Extraction Agent for knowledge graph construction.

## 边类型选择决策树

问自己以下问题来选择正确的边类型:

### 1. 是结构关系吗?
- A 是 B 的一种? → **IsA**
  - 例: "正方形 IsA 多边形", "鲸鱼 IsA 哺乳动物"
- A 是 B 的一部分? → **PartOf**
  - 例: "边 PartOf 三角形", "章节 PartOf 书籍", "心脏 PartOf 人体"
- A 包含 B? → **HasPart** (PartOf 的反向)
  - 例: "汽车 HasPart 引擎"

### 2. 是因果/使能关系吗?
- A 导致 B 发生? → **Causes**
  - 例: "加热 Causes 水沸腾", "地震 Causes 海啸"
- A 使 B 成为可能? → **Enables**
  - 例: "氧气 Enables 燃烧", "语言 Enables 沟通"
- A 阻止 B? → **Prevents**
  - 例: "疫苗 Prevents 感染", "绝缘体 Prevents 导电"

### 3. 是对比关系吗?
- A 和 B 是对立/对比概念? → **Contrasts**
  - 例: "有理数 Contrasts 无理数", "酸 Contrasts 碱"
- A 和 B 相似? → **SimilarTo**
  - 例: "椭圆 SimilarTo 圆"

### 4. 是属性关系吗?
- B 是 A 的特征/属性? → **HasProperty**
  - 例: "正方形 HasProperty 四条等边", "质数 HasProperty 只能被1和自身整除"

### 5. 是时间关系吗?
- A 发生在 B 之前? → **Before**
  - 例: "文艺复兴 Before 工业革命"
- A 发生在 B 之后? → **After**
  - 例: "二战 After 一战"

### 6. 是论证关系吗?
- A 支持/证明 B? → **Supports**
  - 例: "化石证据 Supports 进化论"
- A 反驳/反对 B? → **Attacks**
  - 例: "反例 Attacks 假说"

### 7. 都不是?
- 只有在以上都不适用时 → **RelatedTo**
- ⚠️ 如果选择 RelatedTo，必须在 annotation 中解释为什么其他类型都不适用
- 例: "咖啡 RelatedTo 早晨" (关联但无明确因果/结构关系)

## 输出示例

{
  "relations": [
    {
      "id": "rel_001",
      "source_id": "entity_wait",
      "target_id": "entity_cv",
      "type": "PartOf",
      "confidence": 0.95,
      "evidence": "A condition variable has two operations: wait() and signal()",
      "reasoning": "wait() is explicitly stated as one of two operations OF condition variable"
    }
  ]
}
"""
```

---

## 附录: Ground Truth 统计对照

### threads-cv Ground Truth

**节点类型分布**:
- Concept: 11
- Method: 2
- Proposition: 2
- Agent: 2

**边类型分布**:
- PartOf: 4
- Enables: 3
- RelatedTo: 5
- Contrasts: 2
- HasProperty: 2
- Causes: 1

**核心节点** (8个):
1. Condition Variable
2. wait()
3. signal()
4. Lock/Mutex
5. Producer/Consumer Problem
6. Bounded Buffer
7. Mesa Semantics
8. Use While Loop Rule

---

*本日志随实验进展持续更新*
