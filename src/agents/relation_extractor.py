"""
Relation extraction agent.

Identifies relationships between entities.
"""

import json
from typing import Any

from ..schema.nodes import Node
from ..schema.edges import Edge, EdgeType, EdgeSource, ExtractionMethod
from .base import BaseAgent


class RelationExtractor(BaseAgent):
    """
    Extract relationships between entities.

    Takes entities and source text, identifies connections.
    """

    SYSTEM_PROMPT = """You are an expert Relation Extraction Agent for knowledge graph construction.

Your task is to identify relationships between the provided entities based on the source text.

## 边类型选择决策树

问自己以下问题来选择正确的边类型:

### 1. 是结构关系吗?
- A 是 B 的一种? → **IsA**
  - 例: "正方形 IsA 多边形", "鲸鱼 IsA 哺乳动物"
- A 是 B 的一部分? → **PartOf**
  - 例: "边 PartOf 三角形", "章节 PartOf 书籍"

### 2. 是因果/使能关系吗?
- A 导致 B 发生? → **Causes**
  - 例: "加热 Causes 水沸腾", "地震 Causes 海啸"
- A 使 B 成为可能? → **Enables**
  - 例: "氧气 Enables 燃烧", "语言 Enables 沟通"
- A 阻止 B? → **Prevents**
  - 例: "绝缘体 Prevents 导电", "疫苗 Prevents 感染"

### 3. 是对比关系吗?
- A 和 B 是对立/对比概念? → **Contrasts**
  - 例: "有理数 Contrasts 无理数", "酸 Contrasts 碱"

### 4. 是属性关系吗?
- B 是 A 的特征/属性? → **HasProperty**
  - 例: "正方形 HasProperty 四条等边", "质数 HasProperty 只能被1和自身整除"

### 5. 是时间关系吗?
- A 发生在 B 之前? → **Before**
  - 例: "文艺复兴 Before 工业革命"

### 6. 是论证关系吗?
- A 支持/证明 B? → **Supports**
  - 例: "化石证据 Supports 进化论"
- A 反驳/反对 B? → **Attacks**
  - 例: "反例 Attacks 假说"

### 7. 都不是?
- 只有在以上都不适用时 → **RelatedTo**
- ⚠️ 如果选择 RelatedTo，必须在 reasoning 中解释为什么其他类型都不适用
- 例: "咖啡 RelatedTo 早晨" (关联但无明确因果/结构关系)

## Guidelines

1. Only create relations between entities in the provided list
2. Use the source text to justify each relation
3. Assign confidence based on how explicit the relation is
4. **Strongly prefer specific types over RelatedTo** - RelatedTo should be <40% of relations
5. Include evidence text and reasoning for each relation

## Output Format

```json
{
  "relations": [
    {
      "id": "rel_001",
      "source_id": "entity_001",
      "target_id": "entity_002",
      "type": "PartOf",
      "confidence": 0.9,
      "evidence": "text span showing the relation",
      "reasoning": "Why this type was chosen"
    }
  ]
}
```"""

    def get_system_prompt(self) -> str:
        return self.SYSTEM_PROMPT

    def format_input(
        self,
        text: str,
        entities: list[Node],
        document_id: str,
        **kwargs: Any,
    ) -> str:
        """
        Format input for relation extraction.

        Args:
            text: Source text
            entities: Entities extracted from this text
            document_id: Source document identifier
        """
        prompt_parts = []

        # List entities
        prompt_parts.append("## Entities to Connect\n\n")
        for entity in entities:
            prompt_parts.append(
                f"- **{entity.id}** [{entity.type.value}]: {entity.label}\n"
                f"  Definition: {entity.definition}\n"
            )

        prompt_parts.append("\n## Source Text\n\n")
        prompt_parts.append(text)
        prompt_parts.append(f"\n\n## Document ID: {document_id}")

        return "".join(prompt_parts)

    def parse_output(self, response: str) -> list[Edge]:
        """
        Parse LLM response into Edge objects.

        Args:
            response: Raw LLM response text

        Returns:
            List of extracted Edge objects
        """
        # Extract JSON from response
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start == -1 or end == 0:
                return []

            json_str = response[start:end]
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return []

        relations = data.get("relations", [])
        edges: list[Edge] = []

        for relation in relations:
            try:
                # Map string type to EdgeType enum
                edge_type_str = relation.get("type", "RelatedTo")
                try:
                    edge_type = EdgeType(edge_type_str)
                except ValueError:
                    edge_type = EdgeType.RELATED_TO

                edge = Edge(
                    id=relation.get("id", f"rel_{len(edges):04d}"),
                    source_id=relation.get("source_id", ""),
                    target_id=relation.get("target_id", ""),
                    type=edge_type,
                    confidence=relation.get("confidence", 0.5),
                    source=EdgeSource(
                        document_id=relation.get("document_id", "unknown"),
                        extraction_method=ExtractionMethod.EXPLICIT,
                    ),
                    annotation=relation.get("evidence"),
                )
                edges.append(edge)
            except Exception:
                continue  # Skip malformed relations

        return edges
