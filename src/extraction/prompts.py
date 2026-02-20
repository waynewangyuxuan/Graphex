"""Extraction prompts and schema constants for structured KG extraction."""

ENTITY_TYPES = ["Concept", "Method", "Event", "Agent", "Claim", "Fact"]

EDGE_TYPES = [
    "IsA", "PartOf", "Causes", "Enables", "Prevents",
    "Before", "HasProperty", "Contrasts", "Supports", "Attacks",
]

EXTRACTION_INSTRUCTION = """You are extracting a knowledge graph from educational/technical text.

## Task
Extract entities and relationships that represent the **knowledge being taught**.

## Entity Types
- Concept: Abstract ideas being explained (e.g., "Condition Variable", "Bounded Buffer")
- Method: Operations/procedures being taught (e.g., "wait()", "signal()")
- Event: Historical events relevant to understanding
- Agent: People whose IDEAS are being taught (not authors/editors)
- Claim: Rules/best practices advocated (e.g., "Always use while loops")
- Fact: Verified factual statements

## Relationship Types
- IsA: A is a kind of B
- PartOf: A is part of B
- Causes: A causes B to happen
- Enables: A makes B possible
- Prevents: A blocks/stops B
- Before: A happens before B
- HasProperty: B is a property/attribute of A
- Contrasts: A and B are opposing/contrasting
- Supports: A provides evidence for B
- Attacks: A refutes/undermines B

## Rules
1. Only extract concepts the document is TEACHING, not just mentioning
2. Skip filenames, author names, code variable names unless they ARE the concept
3. Every relationship must have a specific type - if none fits, don't create it
4. Quality over quantity: fewer precise extractions > many vague ones
5. Assign importance: "core" (central to learning), "supporting" (background), "peripheral" (briefly mentioned)

## Output: Return ONLY valid JSON, no markdown fences.
{
  "entities": [
    {
      "id": "e1",
      "type": "Concept",
      "label": "Short Label",
      "definition": "Clear definition in 1-3 sentences.",
      "importance": "core"
    }
  ],
  "relationships": [
    {
      "source": "e1",
      "target": "e2",
      "type": "PartOf",
      "evidence": "brief text evidence"
    }
  ]
}"""
