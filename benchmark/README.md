# Graphex Benchmark System

## 目的

批量测试知识图谱提取质量，通过对比系统输出与人工标注的 Ground Truth 来评估和改进。

## 文件结构

```
benchmark/
├── README.md                    # 本文件
├── datasets/                    # 测试数据集
│   ├── papers/                  # 学术论文类
│   │   ├── mirothinker/
│   │   │   ├── source.pdf       # 原始 PDF
│   │   │   ├── source.txt       # 提取的纯文本
│   │   │   ├── ground_truth.json # 人工标注的标准答案
│   │   │   ├── output.json      # 系统生成结果
│   │   │   └── evaluation.md    # 评估报告
│   │   ├── threads-cv/
│   │   └── threads-bugs/
│   ├── textbooks/               # 教科书类
│   ├── articles/                # 文章类
│   └── narratives/              # 叙事类
│
├── templates/                   # 模板
│   ├── ground_truth_template.json
│   └── evaluation_template.md
│
├── scripts/                     # 评估脚本
│   ├── evaluate.py              # 对比评估
│   └── batch_test.py            # 批量测试
│
└── results/                     # 汇总结果
    └── summary.md
```

## Ground Truth 标注规范

### Node 标注原则

1. **核心概念优先** - 只标注对理解文档核心内容必要的概念
2. **忽略元信息** - 不标注作者、日期、文件名等元信息（除非是分析对象）
3. **适当粒度** - 保持 L2-L3 粒度，不要太细也不要太粗
4. **不重复** - 确保没有重复实体

### Edge 标注原则

1. **类型明确** - 尽量使用具体关系类型，避免 RelatedTo
2. **有理有据** - 每个关系都应该能在原文找到依据
3. **核心关系优先** - 优先标注对理解核心内容重要的关系

### Node 数量参考

| 文档类型 | 预期 Node 数量 |
|---------|---------------|
| 短论文 (8-10页) | 15-30 |
| 长论文 (15-20页) | 30-50 |
| 教科书章节 | 20-40 |
| 文章 | 10-25 |

## 评估维度

### 定性评估

1. **覆盖率** - Ground Truth 中的概念有多少被系统提取？
2. **准确率** - 系统提取的概念有多少是正确的？
3. **关系质量** - 关系类型是否正确？是否有意义？
4. **噪声** - 有多少无关紧要的信息被提取？

### 可选定量指标

- Precision: 正确提取 / 总提取
- Recall: 正确提取 / Ground Truth 总数
- F1: 综合指标

## 工作流程

1. **收集测试文档** - 从不同来源收集多种类型文档
2. **人工标注** - 为每个文档创建 Ground Truth
3. **运行系统** - 批量处理所有文档
4. **对比评估** - 比较输出与 Ground Truth
5. **分析问题** - 识别系统的弱点和改进方向
6. **迭代改进** - 调整 Prompt/Pipeline，重新测试
