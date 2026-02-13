# Schema 变更日志

本文档记录 Node/Edge Schema 的重要变更历史。

---

## 2026-02-12: 重大改进 - 移除 RelatedTo 边类型

### 背景

在 benchmark 测试中发现：
- **RelatedTo 滥用**：76-88% 的边被归类为 RelatedTo
- **信息价值低**：RelatedTo 只表示"两个节点相关"，但没有说明具体关系
- **懒惰分类**：成为 LLM 的"逃避"选项，避免做出具体判断

### 决策

**完全移除 RelatedTo 边类型**

理由：
1. **信息价值为零**：如果两个节点之间有边，显然它们相关，RelatedTo 没有提供额外信息
2. **强制精确分类**：移除后，LLM 必须选择具体边类型（IsA, PartOf, Causes等）
3. **宁缺毋滥**：如果无法确定具体关系类型，不创建边，而不是创建无意义的 RelatedTo

### Schema 变更

**之前（11 种边类型）**：
```python
class EdgeType(str, Enum):
    IS_A = "IsA"
    PART_OF = "PartOf"
    CAUSES = "Causes"
    ENABLES = "Enables"
    PREVENTS = "Prevents"
    BEFORE = "Before"
    HAS_PROPERTY = "HasProperty"
    CONTRASTS = "Contrasts"
    SUPPORTS = "Supports"
    ATTACKS = "Attacks"
    RELATED_TO = "RelatedTo"  # ❌ 移除
```

**之后（10 种边类型）**：
```python
class EdgeType(str, Enum):
    IS_A = "IsA"
    PART_OF = "PartOf"
    CAUSES = "Causes"
    ENABLES = "Enables"
    PREVENTS = "Prevents"
    BEFORE = "Before"
    HAS_PROPERTY = "HasProperty"
    CONTRASTS = "Contrasts"
    SUPPORTS = "Supports"
    ATTACKS = "Attacks"
    # RelatedTo REMOVED - 宁缺毋滥
```

### Prompt 变更

**决策树第 7 步修改**：

之前：
```
### 7. 都不是?
- 只有在以上都不适用时 → RelatedTo
- 如果选择 RelatedTo，必须解释原因
```

之后：
```
### 7. 都不是? → 不创建边!
- ⚠️ 如果以上所有类型都不适用，不要创建这条边
- 原因: 无法确定具体关系类型的边没有信息价值
- 宁缺毋滥: 只创建能明确分类的边
```

### 测试结果对比

#### 排序算法文本（学术文本）

| 指标 | 有 RelatedTo | 无 RelatedTo | 改进 |
|------|-------------|-------------|------|
| RelatedTo % | 7.7% | 0% | ✅ 完全消除 |
| 总边数 | 13 | 10 | 质量优先 |
| IsA | 23% | 40% | ✅ 提升 |
| HasProperty | 46% | 40% | 稳定 |

#### threads-cv.pdf（技术文档）

| 指标 | 有 RelatedTo | 无 RelatedTo | 改进 |
|------|-------------|-------------|------|
| RelatedTo % | 88.9% | 0% | ✅ 完全消除 |
| 总边数 | 9 | 6 | 质量优先 |
| 主要边类型 | RelatedTo | Enables(50%), HasProperty(33%) | ✅ 有意义 |

### 影响

**积极影响**：
1. ✅ **提高边的信息密度**：每条边都携带具体语义
2. ✅ **强制 LLM 做出判断**：不能用 RelatedTo 逃避
3. ✅ **新边类型被使用**：Enables, Prevents, Contrasts 占比提升

**权衡**：
- ⚠️ **边数量下降**：更严格的筛选标准
- ⚠️ **可能遗漏关系**：某些隐含关系不会被提取
- ✅ **质量 > 数量**：符合知识图谱的设计哲学

### 后续优化方向

1. **增加技术领域边类型**（如需要）：
   - Uses: A 使用 B
   - ImplementedBy: A 由 B 实现
   - DependsOn: A 依赖 B

2. **细化现有类型**：
   - 为技术文档优化 Enables/Prevents 的示例
   - 增加 PartOf 的变体（Contains, ComposedOf）

3. **监控边覆盖率**：
   - 如果边覆盖率过低（<30%节点对），考虑增加边类型
   - 目前：quality > quantity，接受较低覆盖率

---

## 2026-02-12: 新增边类型

### 新增类型

1. **Enables** (Makes possible)
   - 例: "氧气 Enables 燃烧", "语言 Enables 沟通"
   - 用途: 表示使能关系，A 使 B 成为可能

2. **Prevents** (Blocks/stops)
   - 例: "绝缘体 Prevents 导电", "疫苗 Prevents 感染"
   - 用途: 表示阻止关系，A 阻止 B 发生

3. **Contrasts** (Opposition/comparison)
   - 例: "有理数 Contrasts 无理数", "酸 Contrasts 碱"
   - 用途: 表示对比关系，A 和 B 是对立或对比概念

### 理由

Benchmark 测试发现：
- 因果关系需要更细粒度分类（Causes vs Enables vs Prevents）
- 学术/技术文档经常对比概念（需要 Contrasts）
- 这三种关系之前都被归类为 RelatedTo

---

## 2026-02-12: 新增节点类型

### 新增类型

**Method** (Operations, functions, APIs, algorithms)
- 例: "QuickSort", "wait()", "加法运算", "求导"
- 用途: 区分操作/函数与抽象概念

### 理由

技术文档中大量出现操作/函数/API：
- 之前：全部归类为 Concept（不精确）
- 现在：Method vs Concept 区分清晰
- 测试结果：Method 占 25-37%，分类合理

---

## MVP Schema 总结（2026-02-12）

### 节点类型（6 种）

1. **Concept** - 抽象概念、理论、数据结构
2. **Method** - 操作、函数、API、算法 ⭐ 新增
3. **Event** - 有明确时间范围的事件
4. **Agent** - 对内容有实质贡献的人物或组织
5. **Claim** - 最佳实践、规则、观点
6. **Fact** - 经过验证的事实陈述

### 边类型（10 种）

1. **IsA** - 类型归属
2. **PartOf** - 部分-整体
3. **Causes** - 因果关系
4. **Enables** - 使能关系 ⭐ 新增
5. **Prevents** - 阻止关系 ⭐ 新增
6. **Before** - 时间先后
7. **HasProperty** - 属性关系
8. **Contrasts** - 对比关系 ⭐ 新增
9. **Supports** - 论证支持
10. **Attacks** - 论证反驳

**移除**: RelatedTo ❌（信息价值低）

---

## 设计原则

1. **信息价值优先**：每个类型都应携带具体语义
2. **宁缺毋滥**：不确定的分类不如不分类
3. **覆盖常见场景**：支持学术、技术、叙事文本
4. **避免过度细分**：保持 MVP 规模（6 节点，10 边）
