# Knowledge Graph Health Metrics: 认知科学研究综述与指导方针

> **目的**: 基于认知科学研究，建立知识图谱抽取质量的健康指标框架
>
> **核心问题**:
> 1. 输入 token 与输出 node 的健康比例是什么？
> 2. 给定 node 数量，人类可理解的 edge 数量是多少？

---

## 1. 认知科学基础研究

### 1.1 Miller's Law: 工作记忆容量

**原始研究**: Miller, G. A. (1956). "The Magical Number Seven, Plus or Minus Two"

**关键发现**:
- 人类短期记忆容量: **7 ± 2 个 chunks**
- 但这取决于 chunk 的复杂性:
  - 数字: ~7 个
  - 字母: ~6 个
  - 单词: ~5 个
  - 复杂概念: **4-5 个**

**对知识图谱的启示**:
- 单个视图中的 **核心节点不应超过 5-7 个**
- 复杂概念需要分层展示
- Chunking（概念聚类）可以帮助理解更大的图

> **Source**: [Miller's Law - Laws of UX](https://lawsofux.com/millers-law/), [Wikipedia](https://en.wikipedia.org/wiki/The_Magical_Number_Seven,_Plus_or_Minus_Two)

### 1.2 Network Visualization 可扩展性研究

**关键研究**: Yoghourdjian et al. - "Scalability of Network Visualisation from a Cognitive Load Perspective"

**实验设计**: 测试 25-175 节点、不同密度的图，任务是找最短路径

**核心发现**:

| 图类型 | 可理解阈值 | 显著困难阈值 |
|--------|-----------|-------------|
| 低密度图 | ~75 节点 | **>100 节点** |
| 高密度图 | ~40 节点 | **>50 节点** |

**生理指标**: 使用 EEG、瞳孔扩张、心率变异性测量认知负荷
- 认知负荷随复杂度上升
- **超过某个阈值后负荷下降** = 用户放弃理解

> **Source**: [arXiv:2008.07944](https://arxiv.org/abs/2008.07944), [PubMed](https://pubmed.ncbi.nlm.nih.gov/33301404/)

### 1.3 Ghoniem et al. 图可读性研究 (2004, 2005)

**实验设计**: Node-link vs Matrix 表示，随机图

| 图规模 | 节点数 | 边密度 |
|--------|--------|--------|
| 小 | 20 | 0.2, 0.4, 0.6 |
| 中 | 50 | 0.2, 0.4, 0.6 |
| 大 | 100 | 0.2, 0.4, 0.6 |

**关键发现**:
- **小图 (20节点)**: Node-link 表现最佳
- **随规模和密度增加**: 性能显著下降
- **原因**: 边重叠、视觉混乱

> **Source**: [Understanding Node-Link and Matrix Visualizations](https://donghaoren.org/publications/netsci19-nodelink-matrix.pdf)

### 1.4 Concept Map 复杂度研究

**关键研究**: "How the design and complexity of concept maps influence cognitive learning processes"

**核心发现**:

1. **节点数量与学习负担**:
   - "The condition with many nodes could create a feeling that learners need to internalize as much as possible"
   - 需要足够的工作记忆容量

2. **结构显著性影响迷失感**:
   - 低显著性结构 → 增加迷失感
   - 迷失感 → 增加外在认知负荷

3. **专家 vs 新手**:
   - 专家能处理更多节点，因为他们能区分重要性
   - **专业发展后节点数反而减少** = 能识别什么是核心

> **Source**: [PMC8788906](https://pmc.ncbi.nlm.nih.gov/articles/PMC8788906/), [Springer](https://link.springer.com/article/10.1007/s11423-022-10083-2)

### 1.5 Kintsch 的 Construction-Integration 模型

**核心概念**:
- **命题 (Proposition)**: 文本的基本语义单元
- **文本基础 (Textbase)**: 文本显式含义的表示
- **情境模型 (Situation Model)**: 读者对所描述情境的心理表示

**关键发现**:
- **回忆取决于命题数量，而非词汇数量**
- 命题倾向于整体回忆或完全不回忆
- 人们根据命题结构中的接近性回忆，而非实际文本顺序

**命题密度**:
- 命题密度 = ideas expressed per word
- 高命题密度 → 老年人理解困难
- 需要平衡密度与可理解性

> **Source**: [Kintsch CI Model](https://verbs.colorado.edu/~mpalmer/Ling7800/Kintsch.pdf), [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0166411508615514)

### 1.6 实体密度研究

**NER 研究发现**:
- 实体密度 = entities per 1,000 words
- 示例值: **0.65 entities per 1,000 words** (某网页分析)
- 高质量内容: "balance - enough prominent entities to anchor content without being repetitive"

**KGGen 研究** (2025):
- 对完整小说 (1M characters) 进行 KG 抽取
- 通过实体合并实现 **22.4% 实体减少**, **23% 边减少**
- 规模越大，去重效果越好

> **Source**: [KGGen arXiv](https://arxiv.org/html/2502.09956v2)

---

## 2. 健康指标框架

基于以上研究，建立以下指标体系：

### 2.1 Token-to-Node Ratio (输入压缩率)

```
压缩率 = Input Tokens / Output Nodes
```

| 压缩率范围 | 含义 | 适用场景 | 认知科学依据 |
|-----------|------|---------|-------------|
| **<50** | 过度抽取 | ❌ 可能大量噪声 | 超过工作记忆容量 |
| **50-150** | 高细粒度 | 密集技术文档 | 每个概念需要定义空间 |
| **150-400** | 中等细粒度 | 教科书章节、论文 | 平衡深度与广度 |
| **400-800** | 低细粒度 | 综述、概述 | 只抓核心概念 |
| **>800** | 过度压缩 | ⚠️ 可能遗漏重要概念 | 信息损失 |

**推荐**: 教科书/技术文档 **200-350 tokens/node**

### 2.2 Edge-to-Node Ratio (图密度系数)

```
密度系数 = Edges / Nodes
```

| 密度系数 | 图结构 | 人类理解性 | 网络科学依据 |
|----------|--------|-----------|-------------|
| **<0.8** | 森林/稀疏 | ⚠️ 可能断裂 | 孤立节点问题 |
| **0.8-1.2** | 树形结构 | ✅ 易于跟踪 | 层次清晰 |
| **1.2-2.0** | 中等连接 | ✅ **理想范围** | 有交叉但可管理 |
| **2.0-3.0** | 较密连接 | ⚠️ 需要分层 | 开始视觉混乱 |
| **>3.0** | 密集网络 | ❌ 信息过载 | "hairball" 效应 |

**推荐**: 目标密度系数 **1.2-1.8**

### 2.3 Average Degree (平均度数)

```
平均度数 = 2 × Edges / Nodes
```

| 平均度数 | 理解难度 | 阈值来源 |
|----------|---------|---------|
| **1-2** | 简单，近似树 | 易于追踪路径 |
| **2-3** | **理想范围** | 有连接但不过载 |
| **3-4** | 中等，需认知努力 | 接近 Ghoniem 阈值 |
| **4-5** | 困难 | 开始超出工作记忆 |
| **>5** | 很困难 | 需要交互/过滤 |

**推荐**: 平均度数 **2.4-3.6**

### 2.4 Core Node Ratio (核心节点比例)

基于 Miller's Law 和概念图研究：

```
核心节点比例 = Core Nodes / Total Nodes
```

| 比例 | 含义 | 依据 |
|------|------|------|
| **<15%** | 核心不突出 | 缺乏焦点 |
| **15-30%** | **理想范围** | 符合 Miller's Law (5-7 core in 20-30 total) |
| **30-50%** | 可接受 | 小图可以 |
| **>50%** | 分层不清 | 什么都是"核心" = 什么都不是核心 |

**推荐**: 核心节点占 **20-35%**

### 2.5 Isolated Node Ratio (孤立节点比例)

```
孤立节点比例 = Nodes with degree 0 / Total Nodes
```

| 比例 | 评价 |
|------|------|
| **0%** | ✅ 理想 |
| **<5%** | ✅ 可接受 |
| **5-15%** | ⚠️ 需要检查 |
| **>15%** | ❌ 图不连贯 |

**推荐**: 孤立节点 **<5%**

---

## 3. 按内容类型的具体指标

### 3.1 教科书章节 (Textbook Chapter)

**典型特征**: 3,000-8,000 tokens, 教学导向, 概念层次清晰

| 指标 | 最小值 | 理想值 | 最大值 |
|------|--------|--------|--------|
| **Nodes** | 10 | **15-25** | 40 |
| **Edges** | 12 | **22-40** | 60 |
| **压缩率** | 100 | **200-350** | 600 |
| **密度系数** | 0.9 | **1.3-1.8** | 2.5 |
| **平均度数** | 1.8 | **2.6-3.6** | 5.0 |
| **核心节点数** | 4 | **5-8** | 10 |
| **孤立节点** | 0 | **0** | 2 |

**示例**: threads-cv (~5000 tokens)
- 预期 Nodes: 15-25
- 预期 Edges: 20-35
- 核心概念: 5-7 (Condition Variable, wait, signal, Lock, Producer-Consumer, Mesa Semantics)

### 3.2 研究论文 (Research Paper)

**典型特征**: 8,000-20,000 tokens, 论证导向, 概念更专业

| 指标 | 最小值 | 理想值 | 最大值 |
|------|--------|--------|--------|
| **Nodes** | 15 | **25-45** | 70 |
| **Edges** | 18 | **35-70** | 120 |
| **压缩率** | 150 | **300-500** | 900 |
| **密度系数** | 0.8 | **1.2-1.6** | 2.5 |
| **平均度数** | 1.6 | **2.4-3.2** | 4.5 |
| **核心节点数** | 5 | **7-12** | 15 |
| **孤立节点** | 0 | **0** | 3 |

**示例**: MiroThinker paper (~15000 tokens)
- 预期 Nodes: 30-45
- 预期 Edges: 40-65
- 核心概念: 8-12 (MiroThinker, Interactive Scaling, ReAct, RL Training, Benchmarks...)

### 3.3 技术文档 (Technical Documentation)

**典型特征**: 2,000-10,000 tokens, 操作导向, API/方法密集

| 指标 | 最小值 | 理想值 | 最大值 |
|------|--------|--------|--------|
| **Nodes** | 8 | **15-30** | 50 |
| **Edges** | 10 | **20-45** | 80 |
| **压缩率** | 80 | **150-300** | 500 |
| **密度系数** | 1.0 | **1.4-2.0** | 2.8 |
| **平均度数** | 2.0 | **2.8-4.0** | 5.5 |
| **核心节点数** | 3 | **5-10** | 12 |
| **Method 类型占比** | 20% | **30-50%** | 60% |

**特点**: Method 类型节点占比更高

### 3.4 新闻/文章 (News Article)

**典型特征**: 500-2,000 tokens, 事件导向, 信息密度低

| 指标 | 最小值 | 理想值 | 最大值 |
|------|--------|--------|--------|
| **Nodes** | 5 | **8-15** | 25 |
| **Edges** | 5 | **10-20** | 35 |
| **压缩率** | 50 | **100-200** | 350 |
| **密度系数** | 0.8 | **1.2-1.5** | 2.0 |
| **Event/Agent 类型占比** | 30% | **40-60%** | 70% |

**特点**: Event 和 Agent 类型节点占比更高

### 3.5 综述/摘要 (Review/Summary)

**典型特征**: 变化大, 概述导向, 广度优先

| 指标 | 最小值 | 理想值 | 最大值 |
|------|--------|--------|--------|
| **压缩率** | 300 | **500-1000** | 1500 |
| **密度系数** | 0.6 | **1.0-1.4** | 2.0 |
| **核心节点比例** | 30% | **40-60%** | 70% |

**特点**: 压缩率高，核心节点比例高

---

## 4. 质量检查清单

### 4.1 必须通过的检查 (Hard Constraints)

- [ ] **Edge > 0**: 必须有边，不能是孤立节点集合
- [ ] **无重复节点**: 同一概念不应出现多次
- [ ] **核心概念覆盖**: 文档标题/主题词应有对应节点
- [ ] **孤立节点 < 10%**: 绝大多数节点应该连接
- [ ] **无噪声节点**: 不应包含文件名、页码、Copyright 作者

### 4.2 应该通过的检查 (Soft Constraints)

- [ ] **压缩率在合理范围**: 根据内容类型
- [ ] **密度系数 1.0-2.5**: 不太稀疏也不太密集
- [ ] **平均度数 2-4**: 适度连接
- [ ] **核心节点 20-35%**: 有明确焦点

### 4.3 红旗警告 (Red Flags)

| 现象 | 可能原因 | 建议行动 |
|------|---------|---------|
| Edge = 0 | Relation Extraction 失败 | 检查 Pipeline 流程 |
| Nodes < 5 (长文档) | 过度过滤 | 调低 Grounding 阈值 |
| Nodes > 100 | 过度抽取 | 添加重要性过滤 |
| 密度 > 4 | 关系过度泛化 | 收紧关系类型 |
| 重复节点 | 去重失败 | 检查 Entity Registry |
| 大量文件名节点 | First-Pass 未生效 | 检查 Prompt |

---

## 5. 实际案例对照

### 5.1 threads-cv Ground Truth

**输入**: ~5000 tokens

| 指标 | 实际值 | 理想范围 | 评价 |
|------|--------|---------|------|
| Nodes | 17 | 15-25 | ✅ |
| Edges | 15 | 20-35 | ⚠️ 略低 |
| 压缩率 | 294 | 200-350 | ✅ |
| 密度系数 | 0.88 | 1.3-1.8 | ⚠️ 略低 |
| 平均度数 | 1.76 | 2.6-3.6 | ⚠️ 略低 |
| 核心节点 | 8 (47%) | 5-8 (20-35%) | ⚠️ 比例高 |
| 孤立节点 | 2 | 0 | ⚠️ |

**诊断**: Ground Truth 边数偏少，可能遗漏了一些关系

### 5.2 当前 Enhanced Pipeline 输出

**threads-cv_enhanced.json**:

| 指标 | 实际值 | 理想范围 | 评价 |
|------|--------|---------|------|
| Nodes | 5 | 15-25 | ❌ 严重不足 |
| Edges | **0** | 20-35 | ❌ **完全失败** |
| 压缩率 | 1000 | 200-350 | ❌ 过度压缩 |
| 密度系数 | 0 | 1.3-1.8 | ❌ |
| 重复节点 | 1 | 0 | ❌ |

**诊断**: Pipeline 严重故障，需要调试

---

## 6. 参考文献

### 认知科学
- Miller, G. A. (1956). The magical number seven, plus or minus two. *Psychological Review*.
- Kintsch, W. (1988). The role of knowledge in discourse comprehension: A construction-integration model. *Psychological Review*.
- Sweller, J. (1988). Cognitive load during problem solving. *Cognitive Science*.

### 图可视化
- Yoghourdjian, V., et al. (2020). Scalability of Network Visualisation from a Cognitive Load Perspective. [arXiv:2008.07944](https://arxiv.org/abs/2008.07944)
- Ghoniem, M., Fekete, J. D., & Castagliola, P. (2005). On the readability of graphs using node-link and matrix-based representations.
- Huang, W., Eades, P., & Hong, S. H. (2009). Measuring Effectiveness of Graph Visualizations. *Information Visualization*.

### 概念图研究
- Blankenship, J., & Dansereau, D. F. (2000). The effect of animated node-link displays on information recall.
- [How concept map complexity influences learning](https://pmc.ncbi.nlm.nih.gov/articles/PMC8788906/)

### 知识图谱
- KGGen: Extracting Knowledge Graphs from Plain Text with Language Models. [arXiv:2502.09956](https://arxiv.org/html/2502.09956v2)

---

*本文档作为 Graphex 项目的质量指标参考，应在 Pipeline 开发和评估中使用。*

*最后更新: 2026-02-13*
