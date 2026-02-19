# Graphex 工程架构设计

> **版本**：v0.1
>
> **日期**：2026-01-29
>
> **状态**：设计阶段

---

## 目录

1. [问题定义](#1-问题定义)
2. [Chunking 策略](#2-chunking-策略)
3. [Multi-Agent 架构](#3-multi-agent-架构)
4. [Context 管理](#4-context-管理)
5. [完整 Pipeline 设计](#5-完整-pipeline-设计)
6. [技术选型](#6-技术选型)
7. [实施路线图](#7-实施路线图)

---

## 1. 问题定义

### 1.1 核心挑战

我们要从长文档（PDF、论文、书籍）中提取知识图谱，面临三个工程挑战：

| 挑战 | 描述 | 复杂度 |
|------|------|--------|
| **Chunking** | 长文档超出 context window，如何切分？ | 中 |
| **Multi-Agent** | 多个任务需要协作，如何设计 Agent 架构？ | 高 |
| **Context 管理** | 跨 chunk 信息如何保持一致？ | 高 |

### 1.2 设计目标

1. **可执行性**：MVP 可在 2-3 周内实现
2. **可扩展性**：支持后续迭代优化
3. **可验证性**：每个模块可独立测试
4. **质量可控**：有明确的验证和审核机制

---

## 2. Chunking 策略

### 2.1 策略选择

**推荐：递归字符切分 + 语义边界尊重**

| 策略 | 优点 | 缺点 | 推荐度 |
|------|------|------|--------|
| 固定长度 | 简单 | 切断语义 | ★★ |
| **递归切分** | 尊重段落边界 | 需调参 | ★★★★ |
| 语义切分 | 最佳语义 | 计算成本高 | ★★★★ |
| LLM 驱动 | 最高质量 | 成本极高 | ★★ |

### 2.2 推荐参数

```yaml
chunking:
  # 基础参数
  chunk_size: 512          # tokens
  chunk_overlap: 75        # tokens (~15%)

  # 层级切分（可选，Phase 2）
  hierarchical: false
  parent_chunk_size: 2048
  child_chunk_size: 512

  # 切分优先级（递归）
  separators:
    - "\n\n"    # 段落
    - "\n"      # 换行
    - "。"      # 中文句号
    - ". "      # 英文句号
    - " "       # 空格
    - ""        # 字符
```

### 2.3 PDF 处理流程

```
PDF 文件
    ↓
[PDF 解析] Unstructured / PyMuPDF
    ↓
[结构提取] 标题、段落、表格
    ↓
[转 Markdown] 保持层级结构
    ↓
[递归切分] 512 tokens + 15% overlap
    ↓
Chunk 列表 (带元数据)
```

### 2.4 Chunk 数据结构

```typescript
interface Chunk {
  id: string;
  index: number;
  text: string;

  // 元数据
  metadata: {
    document_id: string;
    section_title?: string;      // 所属章节
    page_numbers?: number[];     // 原始页码
    token_count: number;

    // 位置信息
    start_char: number;
    end_char: number;
  };

  // 关联信息（处理后填充）
  extracted_entities?: string[];  // 本 chunk 提取的实体 ID
  extracted_relations?: string[]; // 本 chunk 提取的关系 ID
}
```

---

## 3. Multi-Agent 架构

### 3.1 架构模式选择

**推荐：DAG 流水线 + 中央状态管理**

| 模式 | 优点 | 缺点 | 适用性 |
|------|------|------|--------|
| 串行流水线 | 简单 | 无法并行 | MVP ★★★★★ |
| 并行扇出 | 高效 | 聚合复杂 | Phase 2 |
| 层级监督者 | 可控 | 复杂 | Phase 3 |
| **DAG 图结构** | 灵活 | 设计成本 | 生产环境 |

### 3.2 Agent 职责划分

**MVP 阶段：4 个 Agent**

```
┌─────────────────────────────────────────────────────────┐
│                    Pipeline Controller                   │
│         (非 Agent，负责调度和状态管理)                    │
└────────────────────────┬────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ Chunk       │  │ Entity      │  │ Relation    │
│ Processor   │→ │ Extractor   │→ │ Extractor   │
│ Agent       │  │ Agent       │  │ Agent       │
└─────────────┘  └─────────────┘  └─────────────┘
                         │
                         ▼
                ┌─────────────┐
                │ Validator   │
                │ Agent       │
                └─────────────┘
```

**生产阶段：7 个 Agent**

```
┌─────────────────────────────────────────────────────────┐
│                  Orchestrator Agent                      │
│  (任务分解、调度、错误处理)                               │
└────────────────────────┬────────────────────────────────┘
                         │
    ┌────────────────────┼────────────────────┐
    ▼                    ▼                    ▼
┌────────┐         ┌────────┐          ┌────────┐
│ Doc    │────────▶│ Text   │◀────────│ Schema │
│ Parser │         │ Chunker│          │ Manager│
└────────┘         └────────┘          └────────┘
                         │
    ┌────────────────────┼────────────────────┐
    ▼                    ▼                    ▼
┌────────┐         ┌────────┐          ┌────────┐
│ Entity │────────▶│ Relation│◀────────│ Entity │
│Extract │         │ Extract │          │Resolver│
└────────┘         └────────┘          └────────┘
                         │
                         ▼
                ┌─────────────┐
                │ Validator & │
                │Graph Builder│
                └─────────────┘
```

### 3.3 各 Agent 详细设计

#### Agent 1: Entity Extractor

```yaml
职责: 从文本中提取实体

输入:
  - text: string              # chunk 文本
  - schema: EntitySchema      # 实体类型定义
  - known_entities: Entity[]  # 已知实体（用于对齐）

输出:
  - entities: Entity[]
  - confidence_scores: float[]

Prompt 结构:
  - Role: "Entity Extraction Specialist"
  - Schema: 动态注入实体类型定义
  - Context: 已知实体列表（防止重复创建）
  - Examples: 2-3 个领域相关示例
  - Output Format: JSON

Gleaning（迭代提取）:
  - enabled: chunk token_count > 500   # 短 chunk 信息密度低，gleaning 价值有限
  - max_gleanings: 可调               # 建议从 1 开始；每增 1 轮约 2x token 消耗，召回提升递减
  - continuation_prompt: "可能有遗漏的实体，请继续提取"
  - stop_condition: LLM 回答"无更多"或达到 max_gleanings 上限
```

#### Agent 2: Relation Extractor

```yaml
职责: 识别实体间的关系

输入:
  - text: string
  - entities: Entity[]        # 本 chunk 的实体
  - schema: RelationSchema    # 关系类型定义

输出:
  - relations: Relation[]
  - evidence: TextSpan[]      # 支撑证据

Prompt 结构:
  - Role: "Relation Extraction Specialist"
  - Schema: 动态注入关系类型定义
  - Entities: 本 chunk 已提取的实体
  - Constraints: 关系的类型约束
  - Output Format: JSON
```

#### Agent 3: Validator

```yaml
职责: 验证提取结果的质量

输入:
  - entities: Entity[]
  - relations: Relation[]
  - source_text: string
  - schema: FullSchema

输出:
  - validated_entities: Entity[]
  - validated_relations: Relation[]
  - issues: ValidationIssue[]
  - needs_review: Item[]

验证规则:
  1. Schema 一致性（类型是否在 schema 中）
  2. 证据验证（实体是否在原文中）
  3. 类型约束（关系的源/目标类型是否匹配）
  4. 置信度阈值（低于 0.7 标记待审核）
```

### 3.4 Agent 间通信

```typescript
// 共享状态定义
interface PipelineState {
  // 输入
  document: Document;
  schema: Schema;
  config: Config;

  // 中间状态
  chunks: Chunk[];
  current_chunk_index: number;
  entity_registry: Map<string, Entity>;  // 全局实体注册表

  // 输出
  all_entities: Entity[];
  all_relations: Relation[];

  // 元数据
  errors: Error[];
  processing_log: LogEntry[];
}

// Agent 执行结果
interface AgentResult {
  success: boolean;
  output: any;
  errors?: Error[];
  metrics?: {
    execution_time_ms: number;
    tokens_used: number;
  };
}
```

---

## 4. Context 管理

### 4.1 核心问题

跨 chunk 处理时，如何保持信息一致？

| 问题 | 描述 | 解决方案 |
|------|------|----------|
| 实体重复 | 不同 chunk 提取相同实体 | Entity Registry + 传递已知实体 |
| 指代消解 | "他"指代谁？ | Context 注入 + 后处理合并 |
| 关系跨 chunk | 主语在 chunk 1，宾语在 chunk 2 | 增大 overlap + 后处理 |

### 4.2 Context 构建策略

```python
def build_extraction_context(
    chunk: Chunk,
    entity_registry: EntityRegistry,
    recent_chunks: List[Chunk],
    schema: Schema
) -> str:
    """构建提取用的 context"""

    context_parts = []

    # 1. Schema 定义（固定，约 500 tokens）
    context_parts.append(format_schema(schema))

    # 2. 已知实体列表（动态，控制在 20 个以内）
    relevant_entities = entity_registry.get_relevant_to(chunk.text, limit=20)
    context_parts.append(format_known_entities(relevant_entities))

    # 3. 最近 chunk 的提取结果（滑动窗口，最近 2 个）
    for recent in recent_chunks[-2:]:
        context_parts.append(format_recent_extraction(recent))

    # 4. 当前 chunk
    context_parts.append(f"## 待分析文本\n{chunk.text}")

    return "\n\n".join(context_parts)
```

### 4.3 Entity Registry 设计

```python
class EntityRegistry:
    """全局实体注册表，跨 chunk 维护"""

    def __init__(self):
        self.entities: Dict[str, Entity] = {}
        self.aliases: Dict[str, str] = {}  # alias -> canonical_id
        self.embeddings: Dict[str, np.array] = {}

    def register(self, entity: Entity) -> str:
        """注册新实体，返回规范化 ID"""
        # 1. 检查是否已存在（精确匹配）
        if entity.label in self.aliases:
            return self.aliases[entity.label]

        # 2. 检查相似实体（embedding 相似度）
        similar = self.find_similar(entity, threshold=0.9)
        if similar:
            self.aliases[entity.label] = similar.id
            return similar.id

        # 3. 创建新实体
        entity.id = self._generate_id()
        self.entities[entity.id] = entity
        self.aliases[entity.label] = entity.id
        self.embeddings[entity.id] = self._embed(entity)
        return entity.id

    def get_relevant_to(self, text: str, limit: int = 20) -> List[Entity]:
        """获取与文本相关的实体（用于 context）"""
        text_embedding = self._embed(text)
        similarities = []
        for eid, emb in self.embeddings.items():
            sim = cosine_similarity(text_embedding, emb)
            similarities.append((eid, sim))

        similarities.sort(key=lambda x: x[1], reverse=True)
        return [self.entities[eid] for eid, _ in similarities[:limit]]
```

### 4.4 跨 Chunk 实体合并（Phase 4: Entity Resolution）

```python
def resolve_entities_post_processing(
    all_entities: List[Entity],
    llm: LLM
) -> List[Entity]:
    """Phase 4: 实体消歧与合并

    Strategy 1 (P0) — 描述聚合:
      按 label + aliases 匹配，合并描述，类型取众数，描述过长时用 cheap model 摘要。
      利用 Graphex schema 中已有的 aliases 字段作为匹配键。

    Strategy 2 (Enhancement) — Embedding 聚类:
      处理词法无法捕获的同义词（如 "CV" vs "Condition Variable"），在描述聚合之后运行。
    """

    # 1. 描述聚合（P0）：按 label + aliases 匹配，合并描述和类型
    resolved = aggregate_by_label_and_aliases(all_entities, llm)

    # 2. 基于 embedding 聚类（Enhancement）：处理同义词
    clusters = cluster_by_embedding(resolved, threshold=0.85)

    # 2. 对每个可能的合并，用 LLM 验证
    merged_entities = []
    for cluster in clusters:
        if len(cluster) == 1:
            merged_entities.append(cluster[0])
        else:
            # LLM 判断是否应该合并
            should_merge = llm.verify_merge(cluster)
            if should_merge:
                merged = merge_entities(cluster)
                merged_entities.append(merged)
            else:
                merged_entities.extend(cluster)

    return merged_entities
```

---

## 5. 完整 Pipeline 设计

### 5.1 整体流程

```
                    ┌─────────────────────────────────────┐
                    │           输入层                     │
                    │  PDF / Text / Markdown              │
                    └──────────────┬──────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         文档处理层                                    │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐                 │
│  │ PDF Parser │───▶│ Markdown   │───▶│  Chunker   │                 │
│  │            │    │ Converter  │    │ (512 tok)  │                 │
│  └────────────┘    └────────────┘    └─────┬──────┘                 │
│                                            │                         │
│                                   Chunk[]  │                         │
└──────────────────────────────────────┬─────┴─────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         提取层 (Per Chunk)                           │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                     Context Manager                            │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐   │  │
│  │  │ Schema Cache │  │Entity Registry│  │ Recent Extractions │   │  │
│  │  └──────────────┘  └──────────────┘  └────────────────────┘   │  │
│  └────────────────────────────┬───────────────────────────────────┘  │
│                               │                                      │
│           ┌───────────────────┼───────────────────┐                  │
│           ▼                   ▼                   ▼                  │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐        │
│  │ Entity Extractor│ │Relation Extractor│ │    Validator    │        │
│  │      Agent      │→│      Agent       │→│      Agent      │        │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘        │
│                               │                                      │
│                               ▼                                      │
│                    更新 Entity Registry                              │
│                    存储本 Chunk 结果                                  │
└──────────────────────────────────────┬───────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         后处理层                                     │
│                                                                      │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐  │
│  │ Entity Resolver │───▶│ Relation Merger │───▶│  Graph Builder  │  │
│  │ (跨chunk消歧)    │    │ (去重/合并)     │    │  (构建图谱)     │  │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘  │
│                                                                      │
└──────────────────────────────────────┬───────────────────────────────┘
                                       │
                                       ▼
                    ┌─────────────────────────────────────┐
                    │           输出层                     │
                    │  Knowledge Graph (JSON/Neo4j)        │
                    └─────────────────────────────────────┘
```

### 5.2 状态机定义

```python
from enum import Enum

class PipelineStage(Enum):
    INIT = "init"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EXTRACTING = "extracting"
    POST_PROCESSING = "post_processing"
    BUILDING_GRAPH = "building_graph"
    COMPLETED = "completed"
    ERROR = "error"

class PipelineStateMachine:
    """Pipeline 状态管理"""

    transitions = {
        PipelineStage.INIT: [PipelineStage.PARSING, PipelineStage.ERROR],
        PipelineStage.PARSING: [PipelineStage.CHUNKING, PipelineStage.ERROR],
        PipelineStage.CHUNKING: [PipelineStage.EXTRACTING, PipelineStage.ERROR],
        PipelineStage.EXTRACTING: [PipelineStage.POST_PROCESSING, PipelineStage.ERROR],
        PipelineStage.POST_PROCESSING: [PipelineStage.BUILDING_GRAPH, PipelineStage.ERROR],
        PipelineStage.BUILDING_GRAPH: [PipelineStage.COMPLETED, PipelineStage.ERROR],
    }

    def __init__(self):
        self.current_stage = PipelineStage.INIT
        self.state: PipelineState = {}
        self.checkpoints: List[Checkpoint] = []

    def advance(self, next_stage: PipelineStage):
        if next_stage not in self.transitions[self.current_stage]:
            raise InvalidTransition(f"{self.current_stage} -> {next_stage}")
        self.current_stage = next_stage
        self._save_checkpoint()
```

### 5.3 错误处理

```python
class ErrorHandler:
    """Pipeline 错误处理策略"""

    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self.retry_counts: Dict[str, int] = {}

    def handle(self, error: Exception, context: Dict) -> Action:
        chunk_id = context.get("chunk_id", "unknown")

        # 1. 可重试错误
        if isinstance(error, (APIError, TimeoutError)):
            if self.retry_counts.get(chunk_id, 0) < self.max_retries:
                self.retry_counts[chunk_id] = self.retry_counts.get(chunk_id, 0) + 1
                return Action.RETRY

        # 2. 输出格式错误
        if isinstance(error, OutputValidationError):
            return Action.RETRY_WITH_STRICTER_PROMPT

        # 3. 低置信度
        if isinstance(error, LowConfidenceError):
            return Action.MARK_FOR_REVIEW

        # 4. 不可恢复错误
        return Action.SKIP_AND_LOG
```

---

## 6. 技术选型

### 6.1 核心组件

| 组件 | MVP 选择 | 生产选择 | 理由 |
|------|----------|----------|------|
| **编排框架** | 自定义 Python | LangGraph | MVP 简单，生产需要状态管理 |
| **LLM** | Claude 3.5 Sonnet | Claude 3.5 / GPT-4 | 性价比高 |
| **PDF 解析** | PyMuPDF | Unstructured | MVP 够用，生产需要更强的结构识别 |
| **Chunking** | RecursiveCharacterTextSplitter | 自定义语义切分 | LangChain 内置足够好 |
| **向量数据库** | Chromadb (本地) | Qdrant / Pinecone | 实体消歧用 |
| **图存储** | JSON 文件 | Neo4j / FalkorDB | MVP 无需复杂存储 |

### 6.2 依赖清单

```python
# requirements.txt (MVP)

# LLM
anthropic>=0.18.0

# PDF 处理
pymupdf>=1.23.0

# Chunking
langchain-text-splitters>=0.0.1

# 向量
chromadb>=0.4.0

# 工具
pydantic>=2.0.0
httpx>=0.25.0
tenacity>=8.2.0  # 重试
```

---

## 7. 实施路线图

### 7.1 MVP Phase (2-3 周)

**Week 1: 基础设施**
- [ ] 项目结构搭建
- [ ] PDF 解析模块
- [ ] Chunking 模块
- [ ] 基础 Prompt 模板

**Week 2: 核心 Agent**
- [ ] Entity Extractor Agent
- [ ] Relation Extractor Agent
- [ ] 简单 Pipeline 串联

**Week 3: 验证与调优**
- [ ] Validator Agent
- [ ] Entity Registry
- [ ] 测试与调优
- [ ] 输出格式化

### 7.2 产出物

1. **代码**
   - `/src/pipeline/` - Pipeline 核心
   - `/src/agents/` - 各 Agent 实现
   - `/src/context/` - Context 管理
   - `/src/chunking/` - Chunking 模块

2. **文档**
   - Prompt 模板文档
   - API 文档
   - 测试报告

3. **测试**
   - 3 篇不同类型文档的提取结果
   - 质量评估报告

### 7.3 关键 Milestone

| 时间 | Milestone | 验收标准 |
|------|-----------|----------|
| Week 1 | PDF → Chunks | 能正确切分任意 PDF |
| Week 2 | Chunks → Entities + Relations | 单 chunk 提取准确率 > 70% |
| Week 3 | 完整 Pipeline | 整篇文档提取，实体消歧正常 |

---

## 附录：Prompt 模板示例

### Entity Extraction Prompt

```markdown
# Role
You are an expert Entity Extraction Agent for knowledge graph construction.

# Task
Extract all entities from the given text according to the provided schema.

# Schema
## Entity Types
{{schema.entity_types}}

# Known Entities (do not create duplicates)
{{known_entities}}

# Guidelines
1. Extract ONLY entity types defined in the schema
2. Use exact text spans from the source
3. Assign confidence scores (0.0-1.0)
4. If an entity matches a known entity, use the same ID

# Output Format
```json
{
  "entities": [
    {
      "id": "entity_001",
      "type": "Person",
      "label": "...",
      "text_span": "...",
      "properties": {},
      "confidence": 0.95
    }
  ]
}
```

# Text to Analyze
{{chunk_text}}
```

---

*本文档将随实施进展持续更新。*
