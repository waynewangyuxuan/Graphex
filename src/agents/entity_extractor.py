"""
Entity extraction agent.

Extracts entities (Concept, Event, Agent, Claim, Fact) from text chunks.
"""

import json
from typing import Any

from ..schema.nodes import Node, NodeType, NodeSource, NodeMetadata, Granularity
from .base import BaseAgent


class EntityExtractor(BaseAgent):
    """
    Extract entities from text chunks.

    Uses structured prompts to identify and classify knowledge units.
    """

    SYSTEM_PROMPT = """You are an expert Entity Extraction Agent for knowledge graph construction.

Your task is to extract key entities from the given text according to the schema.

## Entity Types (按重要性排序)

1. **Concept**: 抽象概念、理论、数据结构
   - 例: "多边形", "哺乳动物", "质数", "有理数"

2. **Method**: 操作、函数、API、算法步骤
   - 例: "加法运算", "求导", "排序算法"

3. **Event**: 有明确时间范围的事件
   - 例: "文艺复兴", "工业革命"

4. **Agent**: 对内容有实质贡献的人物或组织
   - 例: "欧几里得" (几何创始人), "牛顿" (力学奠基人)
   - ⚠️ 不包括: 文档作者、版权声明中的名字、参考文献作者

5. **Claim**: 最佳实践、规则、观点
   - 例: "三角形内角和为180度"

6. **Fact**: 经过验证的事实陈述
   - 例: "π是无理数"

## ⚠️ 噪声过滤规则 (重要!)

DO NOT extract as entities:
- 文件名 (*.c, *.py, *.java, *.txt, *.pdf)
- Copyright 声明中的作者名 (© Author Name)
- 参考文献/引用中的作者名
- 代码变量名 (除非代表重要概念)
- 页码、章节号、图表编号
- 过于泛化的词 ("thing", "stuff", "resource", "item")

## 重要性标注

为每个实体标注 importance 级别:
- **core**: 章节标题提到 / 有专门段落解释 / 在总结中强调
- **supporting**: 帮助理解核心概念的辅助概念
- **peripheral**: 提及但非重点的背景信息

## Output Format

Return a JSON object with an "entities" array:

```json
{
  "entities": [
    {
      "id": "entity_001",
      "type": "Concept",
      "label": "Short label",
      "definition": "Clear definition in 1-3 sentences.",
      "importance": "core",
      "text_span": "exact text from source",
      "confidence": 0.95
    }
  ]
}
```"""

    def get_system_prompt(self) -> str:
        return self.SYSTEM_PROMPT

    def format_input(
        self,
        text: str,
        document_id: str,
        known_entities: list[Node] | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Format input for entity extraction.

        Args:
            text: Chunk text to analyze
            document_id: Source document identifier
            known_entities: Previously extracted entities for deduplication
        """
        prompt_parts = []

        # Add known entities if provided
        if known_entities:
            known_list = [
                f"- {e.label} ({e.type.value}): {e.definition[:100]}..."
                for e in known_entities[:20]  # Limit to 20
            ]
            prompt_parts.append("## Known Entities (avoid duplicates)\n")
            prompt_parts.append("\n".join(known_list))
            prompt_parts.append("\n\n")

        # Add the text to analyze
        prompt_parts.append("## Text to Analyze\n\n")
        prompt_parts.append(text)
        prompt_parts.append(f"\n\n## Document ID: {document_id}")

        return "".join(prompt_parts)

    def parse_output(self, response: str) -> list[Node]:
        """
        Parse LLM response into Node objects.

        Args:
            response: Raw LLM response text

        Returns:
            List of extracted Node objects
        """
        # Extract JSON from response
        try:
            # Try to find JSON in the response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start == -1 or end == 0:
                return []

            json_str = response[start:end]
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return []

        entities = data.get("entities", [])
        nodes: list[Node] = []

        for entity in entities:
            try:
                node = Node(
                    id=entity.get("id", f"entity_{len(nodes):04d}"),
                    type=NodeType(entity.get("type", "Concept")),
                    label=entity.get("label", "Unknown"),
                    definition=entity.get("definition", "No definition provided"),
                    source=NodeSource(
                        document_id=entity.get("document_id", "unknown"),
                    ),
                    metadata=NodeMetadata(
                        granularity=Granularity.L2,
                        confidence=entity.get("confidence", 0.5),
                    ),
                )
                nodes.append(node)
            except Exception:
                continue  # Skip malformed entities

        return nodes
