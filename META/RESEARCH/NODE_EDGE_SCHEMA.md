# Node 和 Edge Schema 定义

> **版本**：v0.1 (MVP)
>
> **状态**：待验证
>
> **日期**：2026-01-29

---

## 1. Node Schema

### 1.1 Node 类型（Type）

```yaml
NodeTypes:
  # === 持续体（Endurant）===
  Concept:
    description: "抽象概念或范畴"
    examples: ["民主", "哺乳动物", "算法"]
    typical_input: ["说明文", "定义", "百科"]

  Agent:
    description: "有意识的行动者"
    examples: ["爱因斯坦", "公司", "政府"]
    typical_input: ["叙事", "新闻", "传记"]

  Object:
    description: "具体或抽象的对象"
    examples: ["埃菲尔铁塔", "DNA", "互联网"]
    typical_input: ["说明文", "叙事"]

  # === 偶发体（Perdurant）===
  Event:
    description: "发生的事情，有起止时间"
    examples: ["二战", "产品发布", "实验"]
    typical_input: ["叙事", "新闻", "历史"]

  Process:
    description: "持续进行的活动或变化"
    examples: ["光合作用", "城市化", "学习"]
    typical_input: ["说明文", "科学文献"]

  State:
    description: "持续的状态或条件"
    examples: ["经济衰退", "健康", "和平"]
    typical_input: ["叙事", "分析"]

  # === 概念性（Conceptual）===
  Proposition:
    description: "可判断真假的陈述"
    examples: ["地球围绕太阳转", "该政策有效"]
    typical_input: ["论证文", "论文"]

  Theory:
    description: "解释性框架或模型"
    examples: ["相对论", "进化论", "图式理论"]
    typical_input: ["学术文献", "教科书"]

  Method:
    description: "做事的方法或程序"
    examples: ["科学方法", "敏捷开发", "烹饪步骤"]
    typical_input: ["程序性文本", "教程"]
```

### 1.2 Node 数据结构

```typescript
interface Node {
  // === 必要字段 ===
  id: string;                    // 唯一标识符
  type: NodeType;                // 节点类型
  label: string;                 // 简短标识（2-10字）
  definition: string;            // 核心定义（1-3句，50-150字）

  // === 来源追溯 ===
  source: {
    document_id: string;         // 来源文档
    text_span?: {                // 原文位置
      start: number;
      end: number;
      text: string;
    };
  };

  // === 可选字段 ===
  aliases?: string[];            // 同义词/别名
  examples?: string[];           // 示例

  // === 元数据 ===
  metadata: {
    granularity: 'L1' | 'L2' | 'L3' | 'L4';  // 粒度级别
    abstraction_level?: number;   // 抽象度 0-1
    confidence?: number;          // 置信度 0-1
    created_at: string;           // 创建时间
  };
}
```

### 1.3 粒度级别说明

| 级别 | 名称 | 描述 | 典型示例 |
|-----|------|------|---------|
| L1 | Atomic | 单一事实/命题 | "水的沸点是100°C" |
| L2 | Component | 概念/简单关系 | "沸点"作为一个概念 |
| L3 | Chunk | 主题/知识块 | "物质的相变"主题 |
| L4 | Schema | 完整框架/模型 | "热力学"知识体系 |

---

## 2. Edge Schema

### 2.1 Edge 类型（Type）

```yaml
EdgeTypes:
  # === 分类学关系（Taxonomic）===
  IsA:
    description: "类型归属"
    direction: "有向"
    example: "正方形 IsA 多边形"
    more_examples: ["鲸鱼 IsA 哺乳动物", "质数 IsA 整数"]
    inverse: "HasInstance"

  InstanceOf:
    description: "实例关系"
    direction: "有向"
    example: "π InstanceOf 无理数"
    more_examples: ["地球 InstanceOf 行星"]
    inverse: "HasInstance"

  SubclassOf:
    description: "子类关系"
    direction: "有向"
    example: "哺乳动物 SubclassOf 脊椎动物"
    more_examples: ["整数 SubclassOf 有理数"]
    inverse: "HasSubclass"

  # === 构成关系（Compositional）===
  PartOf:
    description: "部分-整体关系"
    direction: "有向"
    example: "边 PartOf 三角形"
    more_examples: ["章节 PartOf 书籍", "心脏 PartOf 人体"]
    inverse: "HasPart"

  MemberOf:
    description: "成员关系"
    direction: "有向"
    example: "2 MemberOf 偶数集合"
    more_examples: ["员工 MemberOf 公司"]
    inverse: "HasMember"

  MadeOf:
    description: "材质构成"
    direction: "有向"
    example: "水分子 MadeOf 氢原子+氧原子"
    more_examples: ["桌子 MadeOf 木头"]

  # === 属性关系（Attributive）===
  HasProperty:
    description: "具有属性"
    direction: "有向"
    example: "正方形 HasProperty 四条等边"
    more_examples: ["质数 HasProperty 只能被1和自身整除", "圆 HasProperty 无穷对称轴"]

  HasAttribute:
    description: "具有特征"
    direction: "有向"
    example: "三角形 HasAttribute 三个内角和为180°"

  # === 因果关系（Causal）===
  Causes:
    description: "导致、引起"
    direction: "有向"
    example: "加热 Causes 水沸腾"
    more_examples: ["地震 Causes 海啸", "除以零 Causes 未定义"]

  Enables:
    description: "使能、促成"
    direction: "有向"
    example: "氧气 Enables 燃烧"
    more_examples: ["语言 Enables 沟通", "公理 Enables 推导定理"]

  Prevents:
    description: "阻止、预防"
    direction: "有向"
    example: "绝缘体 Prevents 导电"
    more_examples: ["疫苗 Prevents 感染"]

  # === 时间关系（Temporal）===
  Before:
    description: "时间上先于"
    direction: "有向"
    example: "文艺复兴 Before 工业革命"

  After:
    description: "时间上后于"
    direction: "有向"
    example: "二战 After 一战"

  During:
    description: "在...期间"
    direction: "有向"
    example: "经济大萧条 During 两次世界大战之间"

  # === 空间关系（Spatial）===
  LocatedAt:
    description: "位于"
    direction: "有向"
    example: "金字塔 LocatedAt 埃及"

  NearTo:
    description: "邻近"
    direction: "对称"
    example: "地球 NearTo 月球"

  # === 联想关系（Associative）===
  # NOTE: RelatedTo 已在 2026-02-12 从 MVP 中移除
  # RelatedTo:
  #   description: "泛关联（类型不明确时使用）"
  #   direction: "对称"
  #   example: "咖啡 RelatedTo 早晨"
  #   note: "已移除 - 太泛化，如果无法分类则不创建边"

  SimilarTo:
    description: "相似"
    direction: "对称"
    example: "椭圆 SimilarTo 圆"
    more_examples: ["菱形 SimilarTo 正方形"]

  Synonym:
    description: "同义"
    direction: "对称"
    example: "函数 Synonym 映射"

  Antonym:
    description: "反义"
    direction: "对称"
    example: "有理数 Antonym 无理数"
    more_examples: ["酸 Antonym 碱", "正数 Antonym 负数"]

  # === 论证关系（Argumentative）===
  Supports:
    description: "支持"
    direction: "有向"
    example: "化石证据 Supports 进化论"

  Attacks:
    description: "反驳"
    direction: "有向"
    example: "反例 Attacks 假说"
    more_examples: ["黑天鹅 Attacks '所有天鹅都是白的'"]

  Qualifies:
    description: "限定条件"
    direction: "有向"
    example: "'在真空中' Qualifies '光速恒定'"

  # === 话语关系（Discourse）===
  Elaborates:
    description: "展开说明"
    direction: "有向"
    example: "定理证明 Elaborates 定理陈述"

  Contrasts:
    description: "对比"
    direction: "有向"
    example: "有理数 Contrasts 无理数"
    more_examples: ["古典力学 Contrasts 量子力学", "酸 Contrasts 碱"]

  Exemplifies:
    description: "举例说明"
    direction: "有向"
    example: "π Exemplifies 无理数"
    more_examples: ["勾股定理 Exemplifies 几何定理"]
```

### 2.2 Edge 数据结构

```typescript
interface Edge {
  // === 必要字段 ===
  id: string;                    // 唯一标识符
  source_id: string;             // 源节点 ID
  target_id: string;             // 目标节点 ID
  type: EdgeType;                // 关系类型

  // === 方向性 ===
  is_directed: boolean;          // 是否有向（默认 true）

  // === 强度与置信 ===
  strength?: number;             // 关联强度 0-1
  confidence?: number;           // 置信度 0-1

  // === 来源追溯 ===
  source: {
    document_id: string;
    extraction_method: 'explicit' | 'implicit' | 'inferred';
    text_span?: {
      start: number;
      end: number;
      text: string;
    };
  };

  // === 可选字段 ===
  annotation?: string;           // 关系注释（解释为何存在）

  // === 元数据 ===
  metadata: {
    created_at: string;
  };
}
```

---

## 3. 输入类型与 Schema 映射

### 3.1 映射表

| 输入类型 | 优先 Node 类型 | 优先 Edge 类型 | 默认粒度 |
|---------|---------------|---------------|---------|
| **叙事文** | Event, Agent, State | Before, After, Causes, LocatedAt | L2-L3 |
| **说明文** | Concept, Object, Process | IsA, PartOf, HasProperty, Causes | L2 |
| **论证文** | Proposition, Concept | Supports, Attacks, Qualifies, Elaborates | L2-L3 |
| **定义/百科** | Concept, Object | IsA, PartOf, HasProperty | L1-L2 |
| **程序性** | Method, Process, Event | Before, After, Enables, Causes | L2-L3 |

### 3.2 识别规则

**叙事文特征**：
- 有明确时间线
- 有人物/角色
- 有事件序列

**说明文特征**：
- 解释概念或现象
- 定义术语
- 描述结构或过程

**论证文特征**：
- 有明确主张
- 有证据支持
- 有反驳或让步

---

## 4. MVP 简化版本

对于 MVP 阶段，建议使用简化的 schema：

### 4.1 MVP Node 类型（6种）

```yaml
MVP_NodeTypes:
  - Concept    # 概念、理论、数据结构
  - Method     # 操作、函数、API（2026-02-12 新增，解决 wait()/signal() 缺失问题）
  - Event      # 事件
  - Agent      # 人/组织（仅限对内容有实质贡献者）
  - Claim      # 主张/论点/最佳实践
  - Fact       # 事实
```

> **2026-02-12 变更说明**:
> - 新增 `Method` 类型：Benchmark 测试发现缺少此类型导致 wait(), signal() 等核心操作无法被正确提取
> - 明确 `Agent` 仅包含对内容有贡献的人物，排除 copyright 作者和引用作者

### 4.2 MVP Edge 类型（10种）

```yaml
MVP_EdgeTypes:
  - IsA        # 类型归属
  - PartOf     # 部分整体
  - Causes     # 因果
  - Enables    # 使能/促成（2026-02-12 新增）
  - Prevents   # 阻止/预防（2026-02-12 新增）
  - Before     # 时间先后
  - HasProperty # 属性
  - Contrasts  # 对比（2026-02-12 从完整版移入 MVP）
  - Supports   # 支持
  - Attacks    # 反驳
  # NOTE: RelatedTo 已移除！如果无法分类，不创建边
```

> **2026-02-12 变更说明**:
> - 新增 `Enables`: 表示"A 使 B 成为可能"的关系，如 "氧气 Enables 燃烧"
> - 新增 `Prevents`: 表示"A 阻止 B"的关系，如 "绝缘体 Prevents 导电"
> - 移入 `Contrasts`: 表示对比关系，如 "有理数 Contrasts 无理数"
> - **移除 `RelatedTo`**: 这个类型太泛化了——如果两个节点有边，它们当然是"相关的"。
>   移除后，如果 LLM 无法确定具体关系类型，就不应该创建这条边。宁缺毋滥。

---

## 5. 验证清单

在测试中需要验证：

- [ ] Node 类型覆盖率：测试文本中的知识单元是否都能归类
- [ ] Edge 类型覆盖率：文本中的关系是否都能归类
- [ ] 标注一致性：不同人对同一文本的标注是否一致
- [ ] AI 执行准确率：AI 生成的 Node/Edge 是否符合定义
- [ ] 粒度一致性：粒度决策规则是否产生一致结果

---

*本文档为 MVP 版本，将根据测试结果迭代更新。*
