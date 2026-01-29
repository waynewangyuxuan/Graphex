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
    example: "狗 IsA 哺乳动物"
    inverse: "HasInstance"

  InstanceOf:
    description: "实例关系"
    direction: "有向"
    example: "Fido InstanceOf 狗"
    inverse: "HasInstance"

  SubclassOf:
    description: "子类关系"
    direction: "有向"
    example: "哺乳动物 SubclassOf 动物"
    inverse: "HasSubclass"

  # === 构成关系（Compositional）===
  PartOf:
    description: "部分-整体关系"
    direction: "有向"
    example: "引擎 PartOf 汽车"
    inverse: "HasPart"

  MemberOf:
    description: "成员关系"
    direction: "有向"
    example: "员工 MemberOf 公司"
    inverse: "HasMember"

  MadeOf:
    description: "材质构成"
    direction: "有向"
    example: "桌子 MadeOf 木头"

  # === 属性关系（Attributive）===
  HasProperty:
    description: "具有属性"
    direction: "有向"
    example: "冰 HasProperty 冷"

  HasAttribute:
    description: "具有特征"
    direction: "有向"
    example: "人 HasAttribute 身高"

  # === 因果关系（Causal）===
  Causes:
    description: "导致、引起"
    direction: "有向"
    example: "下雨 Causes 路滑"

  Enables:
    description: "使能、促成"
    direction: "有向"
    example: "钥匙 Enables 开门"

  Prevents:
    description: "阻止、预防"
    direction: "有向"
    example: "疫苗 Prevents 感染"

  # === 时间关系（Temporal）===
  Before:
    description: "时间上先于"
    direction: "有向"
    example: "事件A Before 事件B"

  After:
    description: "时间上后于"
    direction: "有向"
    example: "事件B After 事件A"

  During:
    description: "在...期间"
    direction: "有向"
    example: "事件A During 事件B"

  # === 空间关系（Spatial）===
  LocatedAt:
    description: "位于"
    direction: "有向"
    example: "埃菲尔铁塔 LocatedAt 巴黎"

  NearTo:
    description: "邻近"
    direction: "对称"
    example: "咖啡店 NearTo 书店"

  # === 联想关系（Associative）===
  RelatedTo:
    description: "泛关联（类型不明确时使用）"
    direction: "对称"
    example: "咖啡 RelatedTo 早晨"
    note: "仅在无法确定更具体关系时使用"

  SimilarTo:
    description: "相似"
    direction: "对称"
    example: "猫 SimilarTo 老虎"

  Synonym:
    description: "同义"
    direction: "对称"
    example: "car Synonym automobile"

  Antonym:
    description: "反义"
    direction: "对称"
    example: "热 Antonym 冷"

  # === 论证关系（Argumentative）===
  Supports:
    description: "支持"
    direction: "有向"
    example: "证据A Supports 主张B"

  Attacks:
    description: "反驳"
    direction: "有向"
    example: "反例 Attacks 主张"

  Qualifies:
    description: "限定条件"
    direction: "有向"
    example: "条件 Qualifies 主张"

  # === 话语关系（Discourse）===
  Elaborates:
    description: "展开说明"
    direction: "有向"
    example: "句子B Elaborates 句子A"

  Contrasts:
    description: "对比"
    direction: "有向"
    example: "观点A Contrasts 观点B"

  Exemplifies:
    description: "举例说明"
    direction: "有向"
    example: "例子 Exemplifies 概念"
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

### 4.1 MVP Node 类型（5种）

```yaml
MVP_NodeTypes:
  - Concept    # 概念
  - Event      # 事件
  - Agent      # 人/组织
  - Claim      # 主张/论点
  - Fact       # 事实
```

### 4.2 MVP Edge 类型（8种）

```yaml
MVP_EdgeTypes:
  - IsA        # 类型归属
  - PartOf     # 部分整体
  - Causes     # 因果
  - Before     # 时间先后
  - HasProperty # 属性
  - Supports   # 支持
  - Attacks    # 反驳
  - RelatedTo  # 泛关联（兜底）
```

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
