# Pipeline 问题诊断报告

## 📊 数据对比总览 (threads-cv)

| 指标 | 系统输出 | Ground Truth | 匹配率 |
|------|---------|--------------|--------|
| 总节点数 | 19 | 17 | - |
| 核心节点匹配 | 3/8 | 8 | **37.5%** |
| 总边数 | 17 | 17 | - |
| 核心边匹配 | 2/8 | 8 | **25%** |
| RelatedTo 占比 | 76% (13/17) | 29% (5/17) | ❌ |

## 🔍 系统输出 vs Ground Truth 详细对比

### 节点对比

**系统提取的节点:**
```
✅ CONDITION VARIABLES (核心概念)
❌ ARPACI-DUSSEAU (作者 - 噪声)
❌ main-two-cvs-if.c (文件名 - 噪声)
❌ main-two-cvs-while-extra-unlock.c (文件名 - 噪声)
⚠️ buffer (应该是 Bounded Buffer)
❌ main-two-cvs-while.c (文件名 - 噪声)
⚠️ buffer (重复)
❌ ARPACI-DUSSEAU (重复)
❌ Linux man page (噪声)
✅ spurious wakeup (支撑概念)
⚠️ race conditions (应为 Race Condition)
❌ signal/wakeup code (过于具体)
❌ B.W. Lampson (引用作者 - 噪声)
❌ D.R. Redell (引用作者 - 噪声)
⚠️ signaling (应为 signal() 方法)
✅ condition variables (重复)
✅ Mesa semantics (核心概念)
✅ Tony Hoare (支撑概念)
❌ shared resource (过于泛化)
```

**Ground Truth 核心节点 (系统缺失):**
```
❌ wait() - 核心操作，完全缺失
❌ signal() - 核心操作，完全缺失
❌ Lock/Mutex - 关键同步原语，缺失
❌ Producer/Consumer Problem - 主要应用场景，缺失
❌ Bounded Buffer - 核心数据结构，缺失
❌ Use While Loop Rule - 关键最佳实践，缺失
❌ Hoare Semantics - 与 Mesa 对比的概念，缺失
```

### 边类型对比

**系统输出分布:**
- RelatedTo: 13 (76%) ← 问题！
- PartOf: 2 (12%)
- Causes: 1 (6%)
- IsA: 1 (6%)

**Ground Truth 分布:**
- RelatedTo: 5 (29%)
- PartOf: 4 (24%)
- Enables: 3 (18%)
- Contrasts: 2 (12%)
- HasProperty: 2 (12%)
- Causes: 1 (6%)

---

## 🔴 问题根因分析

### 1. Entity Extractor Prompt 问题

**当前 Prompt 的问题:**

```python
# 当前 system prompt (entity_extractor.py:21-58)
"""You are an expert Entity Extraction Agent...

## Entity Types
- Concept: Abstract concepts...
- Event: Things that happen...
- Agent: Conscious actors...
- Claim: Propositions...
- Fact: Verified factual statements...
"""
```

**问题分析:**

| 问题 | 影响 | 严重程度 |
|------|------|---------|
| **无粒度指导** | 提取 `signal/wakeup code` 这种过细概念，缺失 `Producer/Consumer` 这种主题概念 | 🔴 高 |
| **无噪声过滤规则** | 提取作者名、文件名、引用作者作为实体 | 🔴 高 |
| **无重要性标记** | 无法区分核心概念和边缘概念 | 🟡 中 |
| **无领域上下文** | Prompt 是通用的，不理解这是操作系统/并发的文档 | 🟡 中 |
| **无 Method 类型** | `wait()` 和 `signal()` 是方法，但没有这个类型 | 🔴 高 |

**建议修改:**

```python
SYSTEM_PROMPT = """You are an expert Entity Extraction Agent for knowledge graph construction.

## Entity Types (按优先级)

1. **Concept**: 核心抽象概念，如理论、模式、数据结构
2. **Method**: 操作、函数、API（如 wait(), signal(), lock()）  # 新增
3. **Process**: 算法或流程
4. **Agent**: 人物或组织（仅限对内容有贡献的）
5. **Claim/Proposition**: 观点或最佳实践

## 过滤规则 (重要!)

DO NOT extract:
- File names (*.c, *.py, *.java)
- Author names from copyright notices (© AUTHOR)
- Authors from references section
- Code variable names unless they represent concepts
- Page numbers or section numbers

## 重要性判断

Mark entities as:
- "core": 章节主题、核心概念、关键操作
- "supporting": 辅助理解的概念
- "peripheral": 可以忽略的细节
"""
```

---

### 2. Relation Extractor Prompt 问题

**当前 Prompt 的问题:**

```python
# 当前 system prompt (relation_extractor.py:22-62)
"""
## Relation Types
- IsA: Type attribution
- PartOf: Part-whole relation
- Causes: Causation
...
- RelatedTo: Generic association (use only when no specific relation applies)

## Guidelines
4. Prefer specific relation types over RelatedTo
"""
```

**问题分析:**

虽然说了 "Prefer specific relation types over RelatedTo"，但实际输出 76% 是 RelatedTo。

**根本原因:**
1. 没有给出足够的判断标准
2. 没有示例说明什么情况用什么关系
3. `Enables`, `Contrasts`, `HasProperty` 在输出中完全没有被使用

**建议修改:**

```python
SYSTEM_PROMPT = """
## Relation Type Selection Guide (按场景)

**结构关系:**
- IsA: 当 A 是 B 的一种 (e.g., "Mesa Semantics" IsA "Condition Variable Semantics")
- PartOf: 当 A 是 B 的组成部分 (e.g., "wait()" PartOf "Condition Variable")

**因果关系:**
- Causes: 当 A 导致 B 发生 (e.g., "Race Condition" Causes "Bug")
- Enables: 当 A 使 B 成为可能 (e.g., "Lock" Enables "Mutual Exclusion")
- Prevents: 当 A 阻止 B (新增)

**对比关系:**
- Contrasts: 当 A 和 B 是对立或对比 (e.g., "Mesa Semantics" Contrasts "Hoare Semantics")

**属性关系:**
- HasProperty: 当 B 是 A 的特征 (e.g., "Condition Variable" HasProperty "Atomicity")

**⚠️ RelatedTo 使用限制:**
只在以下情况使用 RelatedTo:
- 确实无法归类到上述任何类型
- 关系非常模糊

如果选择 RelatedTo，必须解释为什么其他类型都不适用。
"""
```

---

### 3. Entity Registry 去重问题

**代码分析 (entity_registry.py:40-55):**

```python
def register(self, entity: Node) -> str:
    normalized_label = self._normalize_label(entity.label)  # lowercase + strip
    if normalized_label in self.aliases:
        return self.aliases[normalized_label]

    similar = self.find_similar(entity)
    if similar:
        self.aliases[normalized_label] = similar.id
        return similar.id
    ...
```

**问题:**
- `CONDITION VARIABLES` 和 `condition variables` 都会被 normalize 成 `condition variables`
- 但输出中仍有两个！说明可能是不同 chunk 产生的，第一个注册后第二个没被正确合并

**实际问题:**
查看 `find_similar()` 方法，它用的是 substring matching，但 `condition variables` 在 `condition variables` 中是完全匹配的，应该能检测到。

**推测:** 可能是 `buffer` 的问题 - 两个 buffer 定义不同，没被合并。

**建议改进:**
- 使用 embedding-based 相似度
- 对于同一类型的实体，降低相似度阈值
- 添加 alias 自动检测（如 CV = Condition Variable）

---

### 4. 缺少全局文档理解

**当前架构问题:**

```
PDF → Chunks → 逐个处理 Chunk → 汇总
```

这种架构缺失了"先宏观后微观"的处理方式。

**建议架构:**

```
PDF → 结构分析 → 主题提取 → 核心概念预识别 → Chunks → 带上下文处理 → 汇总 → 后处理
       ↓
    - 章节标题
    - 摘要/引言
    - 关键词/主题
```

**具体改进:**

1. **First-Pass Agent**: 先快速扫描全文，提取：
   - 文档类型（教科书 chapter、论文、文档）
   - 核心主题
   - 关键术语（通常在引言和总结中）

2. **Context Injection**: 在每个 chunk 的 prompt 中注入：
   - "This document is about: {core_topics}"
   - "Key concepts to look for: {key_terms}"

---

### 5. 缺少重要性评分

**问题:** 所有实体一视同仁，无法区分核心 vs 边缘。

**建议:**

1. 在实体提取时让 LLM 标注 importance: core/supporting/peripheral
2. 基于以下规则自动评分：
   - 出现频率
   - 是否在标题/引言中提及
   - 是否有专门段落解释
   - 是否在总结中出现

---

### 6. 缺少后处理/验证

**当前 validator.py 只定义了接口，没有实现实质验证。**

**建议添加的验证规则:**

1. **噪声过滤:**
   - 移除文件名实体
   - 移除 copyright 作者
   - 移除过短（<3字符）的实体

2. **重复合并:**
   - 大小写变体合并
   - 单复数合并
   - 缩写展开

3. **孤立节点处理:**
   - 没有任何边连接的节点标记为可疑

4. **边质量检查:**
   - RelatedTo 超过 50% 时警告
   - 自引用边检测
   - 循环关系检测

---

## 📈 改进优先级

| 优先级 | 改进项 | 预期效果 | 工作量 |
|--------|--------|---------|--------|
| P0 | 优化 Entity Extractor Prompt（添加过滤规则 + Method 类型） | 减少 80% 噪声 | 低 |
| P0 | 优化 Relation Extractor Prompt（添加选择指南） | RelatedTo 降到 <40% | 低 |
| P1 | 添加 First-Pass 文档理解 | 提高核心概念召回率 | 中 |
| P1 | 添加后处理过滤 | 移除残余噪声 | 低 |
| P2 | 添加重要性评分 | 支持结果分层展示 | 中 |
| P3 | 升级 Entity Registry 用 embedding | 更好的去重 | 高 |

---

## 🧪 验证方案

修改后，运行 benchmark 测试：

```bash
python benchmark/run_eval.py --dataset threads-cv
```

预期达标指标：
- 核心节点匹配率: >70%
- 核心边匹配率: >60%
- RelatedTo 占比: <40%
- 噪声实体率: <10%
