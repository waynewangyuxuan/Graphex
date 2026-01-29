# 知识图谱的认知科学基础研究

> **研究目的**：为 Graphex 产品的 Node 和 Edge 设计提供认知科学理论基础
>
> **研究日期**：2026-01-29
>
> **状态**：第一版（待迭代验证）

---

## 目录

1. [阅读理解的认知过程](#1-阅读理解的认知过程)
2. [阅读的 Input 类型与模式](#2-阅读的-input-类型与模式)
3. [Node 的认知科学定义](#3-node-的认知科学定义)
4. [Edge 的认知科学定义](#4-edge-的认知科学定义)
5. [设计原则与实践建议](#5-设计原则与实践建议)
6. [待验证假设](#6-待验证假设)

---

## 1. 阅读理解的认知过程

### 1.1 核心理论框架

#### Kintsch 的建构-整合模型（Construction-Integration Model）

这是当前最具影响力的阅读理解理论。该模型认为理解过程包含两个阶段：

**建构阶段**：
- 读者根据输入文本激活相关概念
- 同时激活多种可能的意义解释
- 基本单位是**命题（propositions）**

**整合阶段**：
- 通过扩散激活机制筛选适当元素
- 不相关或不一致的信息被抑制
- 形成连贯的文本表征

**三层表征**：
1. **表层结构（Surface Structure）**：文字和句法的直接表征
2. **文本基础（Textbase）**：文本命题的层级结构
3. **情境模型（Situation Model）**：文本基础与读者先验知识的整合

> **对产品的启示**：知识图谱应该能够表达这三个层次，用户可能需要在不同层次之间切换。

#### 情境模型理论（Situation Model Theory）

Zwaan 和 Radvansky (1998) 提出情境模型是**多维度的**：
- 时间维度（temporal）
- 空间维度（spatial）
- 因果维度（causal）
- 动机维度（motivational）
- 主角维度（protagonist）

> **对产品的启示**：Edge 的类型体系需要覆盖这些维度。

### 1.2 概念表征理论

#### 双重编码理论（Dual Coding Theory）

Allan Paivio 提出人类心智运作于两类表征：
- **言语系统（Verbal System）**：处理语言信息，使用"词素（logogens）"
- **意象系统（Imagery System）**：处理非言语输入，使用"意象素（imagens）"

具体词汇（如"树"）能同时激活两种编码，记忆更佳。

> **对产品的启示**：Node 可能需要同时支持文本和视觉表征。

#### 扩散激活理论（Spreading Activation Theory）

Collins 和 Loftus (1975) 提出：
- 概念在网络中表征为节点
- 节点通过双向联想链接相互连接
- 激活从被触发的节点扩散到相邻节点
- 激活强度随距离衰减

> **对产品的启示**：这为图谱结构提供了直接的认知科学依据——知识确实是网络形态的。

### 1.3 影响知识保留的关键因素

| 因素 | 机制 | 对产品的启示 |
|------|------|-------------|
| **加工深度** | 语义加工比表面加工记忆更好 | 促进用户主动生成解释 |
| **测试效应** | 检索比重复学习更有效 | 整合主动回忆功能 |
| **间隔重复** | 分布式练习优于集中练习 | 实现间隔复习调度 |
| **先验知识** | 新知识必须与已有知识整合 | 支持知识关联可视化 |
| **元认知** | 自我监控促进学习 | 提供理解度自评工具 |

---

## 2. 阅读的 Input 类型与模式

### 2.1 文本类型分类（学界共识）

基于 Werlich (1976) 的认知导向分类：

| 文本类型 | 对应认知功能 | 典型形式 |
|---------|-------------|---------|
| **叙事型** (Narrative) | 时间中的感知 | 小说、传记、新闻报道 |
| **描写型** (Descriptive) | 空间中的感知 | 景物描写、人物刻画 |
| **说明型** (Expository) | 一般概念的理解 | 教科书、百科条目 |
| **论证型** (Argumentative) | 判断与评价 | 论文、社论、辩论 |
| **指令型** (Instructive) | 规划与行动指导 | 操作手册、食谱 |

### 2.2 阅读模式分类

#### Rosenblatt 的 Efferent vs Aesthetic 阅读

| 维度 | Efferent（信息提取式） | Aesthetic（审美体验式） |
|-----|---------------------|----------------------|
| **关注点** | 信息、要点、可带走的内容 | 体验本身、节奏、意象、情感共鸣 |
| **对措辞的态度** | 不关心具体措辞 | 关注词语选择、韵律、内涵 |
| **目的** | 获取可操作的信息 | 参与审美体验 |

#### 深度学习 vs 表面学习（Marton & Saljo）

| 深度学习 | 表面学习 |
|---------|---------|
| 意图理解意义 | 意图复述内容 |
| 分析、综合、问题解决 | 机械记忆、程序化处理 |
| 建立与先验知识的连接 | 孤立地处理信息 |
| 产生可迁移的理解 | 产生脆弱的、情境依赖的知识 |

### 2.3 Input × 模式交互的认知产物

**核心发现**：同一材料，不同阅读模式会产生不同的认知产物。

| 组合 | 情境模型特征 |
|-----|------------|
| 叙事 + Aesthetic | 沉浸式、情感丰富、角色认同 |
| 叙事 + Efferent | 事件序列提取、因果链识别 |
| 说明 + 深度学习 | 概念网络、原理理解 |
| 论证 + 批判性阅读 | 论证结构、证据评估 |

> **对产品的启示**：不同 Input 类型可能需要不同的 Node/Edge schema；同一文本以不同模式阅读，提取的图谱结构可能不同。

---

## 3. Node 的认知科学定义

### 3.1 Node 对应的心理实体

Node 不对应单一心理实体，而是可以映射到多个认知层次：

| 认知层次 | 心理实体 | 典型内容 | 粒度 |
|---------|---------|---------|-----|
| **原子层** | 命题 (Proposition) | 最小语义单元 | L1 |
| **概念层** | 概念 (Concept) | 范畴知识 | L2 |
| **图式层** | 图式/脚本 (Schema) | 结构化知识 | L3 |
| **情境层** | 情境模型 (Situation Model) | 整合性心理表征 | L4 |

### 3.2 Node 类型体系

**一级分类（基于上层本体论）**：

```
Node Types
├── Endurant（持续体）—— 在时间中持存的实体
│   ├── Concept（概念）
│   ├── Agent（智能体）
│   └── Object（对象）
│
├── Perdurant（偶发体）—— 在时间中展开的事件
│   ├── Event（事件）
│   ├── Process（过程）
│   └── State（状态）
│
└── Conceptual（概念性）—— 纯粹的认知构造
    ├── Proposition（命题）
    ├── Theory（理论）
    └── Method（方法）
```

**基于输入类型的适配**：

| 输入类型 | 优先节点类型 | 粒度倾向 |
|---------|-------------|---------|
| 叙事 | Event, Agent, State | L2-L3 |
| 说明 | Concept, Property | L1-L2 |
| 论证 | Proposition, Theory | L2-L3 |
| 程序性 | Method, Process | L2-L4 |

### 3.3 Node 信息结构

**必要字段**：

| 字段 | 类型 | 说明 |
|-----|------|------|
| `id` | String | 唯一标识符 |
| `type` | Enum | 节点类型 |
| `label` | String | 简短标识名称 |
| `definition` | Text | 核心定义（1-3句） |
| `source` | Reference | 来源信息 |

**扩展字段**：

| 字段 | 类型 | 说明 |
|-----|------|------|
| `aliases` | String[] | 同义词/别名 |
| `examples` | Reference[] | 正例 |
| `counterexamples` | Reference[] | 反例 |
| `abstraction_level` | Float (0-1) | 抽象度 |
| `confidence` | Float (0-1) | 置信度 |
| `granularity` | Enum | 粒度级别 (L1-L4) |

### 3.4 粒度决策规则

**四级粒度模型**：

| 级别 | 名称 | 典型内容 | 时间尺度 |
|-----|------|---------|---------|
| L1 | Atomic | 单一命题/事实 | ~1秒 |
| L2 | Component | 概念/简单技能 | ~10秒 |
| L3 | Chunk | 知识块/主题 | ~1分钟 |
| L4 | Schema | 完整图式/模型 | ~10分钟 |

**决策启发式**：
1. **可独立理解原则**：Node 应能独立被理解
2. **最小完整语义原则**：包含完整表达一个语义单元所需的最少信息
3. **可复用原则**：如果某知识片段在多处被引用，应独立为节点
4. **3-4 子元素规则**：复合节点的直接子元素数量宜控制在 3-4 个

---

## 4. Edge 的认知科学定义

### 4.1 Edge 对应的心理实体

Edge 对应三种相互关联的心理实体：

| 心理实体 | 特性 | 示例 |
|---------|------|------|
| **联想链接** | 无类型、强度可变、双向 | 咖啡 ↔ 早晨 |
| **语义关系** | 有明确类型、有方向 | 狗 → 动物 (ISA) |
| **推理连接** | 支持因果推断 | 下雨 → 路滑 (CAUSES) |

### 4.2 Edge 类型体系

**元类别（Level 1）**：

```
EdgeTypes
├── Taxonomic（分类学关系）
│   ├── IsA, InstanceOf, SubclassOf
│
├── Compositional（构成关系）
│   ├── PartOf, MemberOf, MadeOf
│
├── Attributive（属性关系）
│   ├── HasProperty, HasAttribute
│
├── Causal（因果关系）
│   ├── Causes, Enables, Prevents
│
├── Temporal（时间关系）
│   ├── Before, After, During, Simultaneous
│
├── Spatial（空间关系）
│   ├── LocatedAt, NearTo, ContainedIn
│
├── Associative（联想关系）
│   ├── RelatedTo, SimilarTo, Synonym, Antonym
│
├── Argumentative（论证关系）
│   ├── Supports, Attacks, Qualifies, Concedes
│
└── Discourse（话语关系）
    ├── Elaborates, Contrasts, Exemplifies, Summarizes
```

**基于输入类型的适配**：

| 输入类型 | 核心 Edge 类型 |
|---------|---------------|
| 百科/定义类 | Taxonomic, Compositional |
| 叙事/故事类 | Temporal, Causal, Spatial |
| 说明文 | Taxonomic, Compositional, Causal |
| 论证文 | Argumentative, Discourse |

### 4.3 Edge 信息结构

**必要字段**：

| 字段 | 类型 | 说明 |
|-----|------|------|
| `id` | UUID | 唯一标识符 |
| `source_id` | UUID | 源节点 ID |
| `target_id` | UUID | 目标节点 ID |
| `relation_type` | Enum | 关系类型 |
| `is_directed` | Boolean | 是否有向（默认 true） |

**扩展字段**：

| 字段 | 类型 | 说明 |
|-----|------|------|
| `strength` | Float [0,1] | 关联强度 |
| `confidence` | Float [0,1] | 置信度 |
| `evidence` | Object | 支撑证据 |
| `extraction_method` | Enum | 显式/隐式/推断 |
| `temporal_scope` | TimeRange | 时间有效范围 |
| `annotation` | String | 关系注释 |

### 4.4 特殊关系处理

**隐含关系**：
- 标记 `extraction_method: "implicit"`
- 提供推理链解释
- 通常置信度较低

**跨文档关系**：
- 添加 `scope: "cross_document"`
- 记录来源文档 ID
- 提供关联证据

**时间性关系**：
- 添加 `temporal_scope` 字段
- 记录有效时间范围

---

## 5. 设计原则与实践建议

### 5.1 总体设计原则

| 原则 | 说明 | 认知依据 |
|-----|------|---------|
| **多态 Node** | 同一框架容纳不同粒度 | 知识的多层次表征 |
| **类型化 Edge** | 尽可能给关系明确类型 | 语义关系的明确性 |
| **方向性默认** | Edge 默认有向 | 多数语义关系天然有向 |
| **强度与置信分离** | 分别表示语义强度和确定性 | 认知上是两个独立维度 |
| **证据可追溯** | 每条关系都应能追溯来源 | 支持解释性 |
| **输入类型感知** | 根据文本类型适配 schema | 不同文本的认知结构不同 |

### 5.2 实现优先级建议

**Phase 1（MVP）**：
- 基础 Node 类型：Concept, Event, Proposition
- 基础 Edge 类型：IsA, PartOf, Causes, Supports, RelatedTo
- 单一粒度（L2-L3）
- 单文档处理

**Phase 2**：
- 完整 Node 类型体系
- 完整 Edge 类型体系
- 多粒度支持
- 隐含关系提取

**Phase 3**：
- 多文档综合
- 跨文档关系
- 时间性关系
- 知识演化追踪

---

## 6. 待验证假设

以下假设需要在 MVP 测试中验证：

### 6.1 关于认知模型

1. **假设**：用户能够理解和使用我们定义的 Node 类型分类
   - **验证方法**：用户测试，观察分类准确率

2. **假设**：我们的 Edge 类型体系覆盖了实际文本中的主要关系
   - **验证方法**：对测试文本进行标注，统计未覆盖关系比例

3. **假设**：粒度决策规则能产生一致的切分结果
   - **验证方法**：多人标注一致性测试

### 6.2 关于学习效果

1. **假设**：图谱化表征比线性阅读更有助于理解
   - **验证方法**：对照实验，测试理解度

2. **假设**：显式关系类型比隐式关联更有助于记忆
   - **验证方法**：延迟测试记忆保持率

3. **假设**：不同 Input 类型确实需要不同的 schema
   - **验证方法**：跨类型测试，比较图谱质量

### 6.3 关于 AI 生成

1. **假设**：当前 LLM 能够可靠地执行我们的 Node/Edge 定义
   - **验证方法**：生成测试，人工评估准确率

2. **假设**：Prompt engineering 能够控制生成的粒度
   - **验证方法**：不同粒度指令的生成对比

---

## 参考文献

### 核心认知理论
- Kintsch, W. (1998). Comprehension: A paradigm for cognition
- Collins, A. M., & Loftus, E. F. (1975). A spreading-activation theory of semantic processing
- Paivio, A. (1971). Imagery and verbal processes
- Zwaan, R. A., & Radvansky, G. A. (1998). Situation models in language comprehension and memory

### 阅读理论
- Rosenblatt, L. M. (1978). The reader, the text, the poem
- Marton, F., & Säljö, R. (1976). On qualitative differences in learning

### 知识表示
- ConceptNet 5.5: https://arxiv.org/abs/1612.03975
- WordNet: https://wordnet.princeton.edu/
- DOLCE Upper Ontology

### 学习科学
- Roediger, H. L., & Karpicke, J. D. (2006). Test-enhanced learning
- Craik, F. I., & Lockhart, R. S. (1972). Levels of processing
- Miller, G. A. (1956). The magical number seven

---

*本文档为活文档，将随产品迭代持续更新。*
