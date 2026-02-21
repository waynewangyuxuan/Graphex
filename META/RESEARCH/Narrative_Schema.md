# Narrative Structure Schema

> **版本**: v0.1
> **状态**: Draft
> **日期**: 2026-02-21

---

## 1. 设计动机

v8 实验（Progressive Understanding Pipeline）证明了一个关键发现：

- **Narrative 质量 8/10** — 模型很擅长用文字表达"这段在讲什么"
- **Entity graph 质量 4/10** — 实体抽取充满重复和噪声
- **Relationship graph 质量 3/10** — 边的类型爆炸、方向混乱

根因分析：传统 KG 的 `(Entity, Relation, Entity)` 三元组丢掉了叙事结构——知识之间的教学顺序、论证逻辑、问题-方案的对应关系。这些恰恰是帮助学生理解文本最重要的信息。

**核心转向**：从"抽取概念和关系"转向"抽取叙事结构"。

---

## 2. Schema 概览

```
Narrative Graph = Segments + Discourse Relations + Concept Tags
```

- **Segment**：叙事的最小单元——一个 claim、一个解释、一个例子、一个问题陈述
- **Discourse Relation**：Segment 之间的修辞/逻辑关系
- **Concept Tag**：Segment 提到的关键概念（轻量标签，不是完整实体）

与传统 KG 的区别：

| | 传统 KG | Narrative Graph |
|---|---|---|
| 节点 | 概念/实体 | 叙事片段（作者在说什么） |
| 边 | 语义关系（IsA, PartOf...） | 修辞关系（elaborates, motivates...） |
| 概念 | 一等公民 | 标签/tag，附着在 segment 上 |
| 核心问题 | "世界上有什么东西？" | "作者在教什么？怎么教的？" |

---

## 3. Segment Types

Segment 类型反映作者的**修辞意图**——这段文字在论证中扮演什么角色。

```yaml
SegmentTypes:
  setup:
    description: "设定背景、引入话题、建立前提"
    example: "In the previous chapter, we introduced locks and built concurrent data structures."

  problem:
    description: "提出问题、揭示困难、展示不足"
    example: "Spinning wastes CPU cycles — the child thread spins for an extended period just checking a condition."

  mechanism:
    description: "解释某个机制/概念如何工作"
    example: "A condition variable is an explicit queue that threads put themselves on when a condition is not met."

  example:
    description: "具体代码、场景、实例"
    example: "Figure 30.3 shows the parent-child join pattern using a condition variable and a mutex."

  rule:
    description: "最佳实践、规则、指导原则"
    example: "Always use while loops instead of if statements when checking conditions."

  consequence:
    description: "结果、影响、推论"
    example: "Without proper signaling, threads may sleep forever, leading to deadlock."

  contrast:
    description: "对比两种方案/概念/语义"
    example: "Mesa semantics require re-checking the condition; Hoare semantics guarantee the condition holds."

  summary:
    description: "总结、回顾、要点归纳"
    example: "Condition variables, combined with locks, enable threads to efficiently wait for state changes."
```

**设计原则**：
- 8 种类型，覆盖教科书/技术文档的主要修辞模式
- 类型之间互斥——每个 segment 只有一种主要意图
- 如果难以判断，优先选择更具体的类型

---

## 4. Discourse Relations

连接 segment 的逻辑/修辞关系。每条关系是有向的：`source → target` 意味着 source 在修辞上作用于 target。

```yaml
DiscourseRelations:
  motivates:
    description: "A 引出/激发 B（通常 problem → mechanism）"
    example: "spinning problem motivates condition variables"
    typical: "problem → mechanism, setup → problem"

  elaborates:
    description: "A 展开解释 B（提供更多细节）"
    example: "wait() implementation elaborates condition variable mechanism"
    typical: "mechanism → mechanism, any → any"

  exemplifies:
    description: "A 是 B 的具体实例"
    example: "parent-child join code exemplifies condition variable usage"
    typical: "example → mechanism, example → rule"

  enables:
    description: "A 使 B 成为可能（前置知识/条件）"
    example: "mutex enables condition variable (CV requires mutex for atomicity)"
    typical: "mechanism → mechanism, setup → mechanism"

  complicates:
    description: "A 给 B 带来新问题/限制"
    example: "mesa semantics complicates simple if-check approach"
    typical: "mechanism → mechanism, consequence → rule"

  resolves:
    description: "A 解决 B 提出的问题"
    example: "while-loop rule resolves mesa semantics complication"
    typical: "rule → problem, mechanism → problem"

  contrasts:
    description: "A 与 B 形成对比"
    example: "mesa semantics contrasts hoare semantics"
    typical: "contrast → contrast, mechanism → mechanism"

  leads_to:
    description: "A 在论证中引向 B（顺序/因果）"
    example: "understanding spinning leads_to appreciating sleep/wake"
    typical: "any → any (narrative sequence)"
```

**设计原则**：
- 8 种关系，比传统 KG 的语义关系**更稳定**——判断"A 是否引出了 B"比判断"Mutex IsA SynchronizationPrimitive"容易得多
- 关系类型对应修辞学中的 discourse relations，有成熟的理论基础（RST, PDTB）
- `leads_to` 是最宽松的关系，用于纯粹的叙事顺序

---

## 5. Concept Tags

轻量级概念标签，附着在 segment 上。**不是**独立的实体节点。

```typescript
interface ConceptTag {
  label: string;       // 概念名称，如 "Condition Variable"
  role: "introduces" | "uses" | "deepens";
  // introduces: 本 segment 首次引入此概念
  // uses: 本 segment 引用已知概念
  // deepens: 本 segment 加深/修正对此概念的理解
}
```

Concept tags 的作用：
1. **导航**：学生点击一个 concept，看到所有提到它的 segments
2. **学习追踪**：concept 从 "introduces" → "uses" → "deepens" 的轨迹就是学习路径
3. **搜索**：在多篇文档中通过 concept 建立联系

---

## 6. 完整数据结构

```typescript
interface NarrativeSegment {
  id: string;                    // s1, s2, ...
  type: SegmentType;             // setup, problem, mechanism, ...
  title: string;                 // 一句话标题（学生看到的）
  content: string;               // 2-4 句摘要（这段在说什么）
  concepts: ConceptTag[];        // 涉及的概念
  source_range?: {               // 原文对应位置
    chunk_id: number;
    approx_position: string;     // "beginning" | "middle" | "end"
  };
  importance: "core" | "supporting" | "detail";
}

interface DiscourseEdge {
  source: string;                // segment ID
  target: string;                // segment ID
  type: DiscourseRelationType;   // motivates, elaborates, ...
  annotation?: string;           // 一句话解释为什么有这个关系
}

interface NarrativeGraph {
  // Document-level
  topic: string;
  theme: string;                 // 核心主题句
  learning_arc: string;          // 学习路径概述

  // Graph
  segments: NarrativeSegment[];
  relations: DiscourseEdge[];

  // Derived
  concept_index: {               // 自动聚合
    [concept: string]: string[]; // concept → segment IDs
  };
}
```

---

## 7. 与 Scrollytelling + Semantic Zoom 的对应

| Narrative Schema 元素 | Scrollytelling 表现 | Semantic Zoom 表现 |
|---|---|---|
| `theme` | 标题/开场 | 最高层级（一句话） |
| `learning_arc` | 进度条/路线图 | 第二层级 |
| Core segments | 主故事线中的步骤 | 第三层级（可展开的卡片） |
| Supporting segments | 展开后可见的细节 | 第四层级 |
| Discourse relations | 段落之间的动画连线 | 展开时显示的连接 |
| Concept tags | 可高亮的关键词 | 跨段落导航锚点 |

---

## 8. 预期优势 vs Entity-Edge KG

1. **精度更高**：判断"这段在解释一个机制"比判断"Mutex IsA SynchronizationPrimitive"容易
2. **容错更好**：即使 segment 边界略有偏差，内容摘要仍然有用
3. **学习导向**：直接回答"作者想教什么、怎么教的"
4. **可视化友好**：segment 是有内容的节点（不只是一个标签），展示时更丰富
5. **narrative 质量可复用**：v8 已经证明模型产出的 narrative 质量高

---

*本文档为草案，将根据 threads-cv 测试结果迭代。*
