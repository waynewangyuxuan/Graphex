# Progress Log

Append-only development log. Add new entries at the top.

---

## 2026-02-12

### Completed
- 建立 Benchmark 系统
  - 创建 `benchmark/` 目录结构
  - 创建 Ground Truth 模板 (`ground_truth_template.json`, `evaluation_template.md`)
  - 为三篇测试文档创建 Ground Truth:
    - threads-cv: 17 nodes, 17 edges (8 core each)
    - MiroThinker: 22 nodes, 22 edges (12 core each)
    - threads-bugs: 20 nodes, 20 edges (10 core each)
- 完成 Pipeline 问题诊断
  - 对比 threads-cv 系统输出 vs Ground Truth
  - 核心节点匹配率: 37.5%
  - 核心边匹配率: 25%
  - 识别 6 个主要问题根因
- 创建系统性文档
  - `benchmark/PIPELINE_DIAGNOSIS.md` - 问题诊断报告
  - `Meta/Research/Prompt_Engineering_Log.md` - Prompt 优化追踪日志

### 关键发现

**Entity Extraction 问题**:
| 问题 | 影响 |
|------|------|
| 无噪声过滤规则 | 提取文件名、作者名作为实体 |
| 缺少 Method 类型 | 无法表示 wait(), signal() 等核心操作 |
| 无重要性标注 | 核心概念和边缘提及混淆 |

**Relation Extraction 问题**:
| 问题 | 影响 |
|------|------|
| 边类型选择指南缺失 | 76% 边都是 RelatedTo |
| 无 Enables/Contrasts 使用 | 缺失关键关系类型 |

### Decisions Made
- 建立 Prompt Engineering 实验追踪体系 (EXP-XXX 编号)
- 优先 Prompt 优化 (P0) 而非架构改动
- 目标指标: 核心节点匹配 >70%, RelatedTo <40%

### Blockers / Issues
- 无

### Next
- [ ] 执行 EXP-002: Entity Extractor Prompt v0.2
- [ ] 执行 EXP-003: Relation Extractor Prompt v0.2
- [ ] 重新运行 benchmark 验证改进效果
- [ ] 如果 Prompt 优化效果不足，考虑架构改进 (First-Pass Agent)

---

## 2026-02-01

### Completed
- Project structure initialized with Meta folder hierarchy
- Existing documentation migrated (Product.md, Technical.md, Research docs)
- ADR system set up
- Milestone tracking system created

### Decisions Made
- Focus on core business logic testing before frontend development
- MVP targets Node/Edge schema validation and AI pipeline testing

### Blockers / Issues
- None

### Next
- Begin M1: Core pipeline implementation and testing
- Validate Node/Edge schema with real documents
- Test AI extraction workflow

---

<!-- Template for new entries:

## YYYY-MM-DD

### Completed
-

### Decisions Made
-

### Blockers / Issues
-

### Next
-

-->
