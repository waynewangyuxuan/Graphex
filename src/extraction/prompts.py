"""Extraction prompts and schema constants for structured KG extraction."""

ENTITY_TYPES = ["Concept", "Method", "Event", "Agent", "Claim", "Fact"]

EDGE_TYPES = [
    "IsA", "PartOf", "Causes", "Enables", "Prevents",
    "Before", "HasProperty", "Contrasts", "Supports", "Attacks",
]

# --- Per-chunk prompt (original, for chunked extraction) ---
CHUNK_PROMPT = """You are extracting a knowledge graph from educational/technical text.

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

# --- Whole-document prompt (thorough extraction, no chunking) ---
WHOLE_DOC_PROMPT = """You are building a comprehensive knowledge graph from an entire educational/technical document.

## Task
Extract ALL entities and relationships that represent the knowledge being taught.
Be thorough — cover every concept, mechanism, rule, and person whose ideas the document explains. A typical document of this length should yield 15-25 entities and 15-30 relationships.

## Entity Types
- Concept: Abstract ideas being explained (e.g., "Condition Variable", "Bounded Buffer")
- Method: Operations/procedures being taught (e.g., "wait()", "signal()")
- Event: Historical events relevant to understanding
- Agent: People whose IDEAS are being taught (not authors/editors)
- Claim: Rules/best practices advocated (e.g., "Always use while loops")
- Fact: Verified factual statements

## Relationship Types (use ONLY these types)
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
3. Every relationship must use one of the types listed above — if none fits, don't create it
4. Be thorough: extract BOTH high-level concepts AND specific mechanisms/operations
5. Include supporting concepts, not just the most prominent ones
6. Assign importance: "core" (central to learning), "supporting" (helpful context), "peripheral" (briefly mentioned)
7. For each section of the document, ask: what concepts are being taught here? Extract them all.

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

# --- Two-pass: Entity-only extraction (Pass 1, cheap model) ---
ENTITY_ONLY_PROMPT = """You are extracting entities from an educational/technical document to build a knowledge graph.

## Task
Extract ALL entities that represent the knowledge being taught. Focus ONLY on entities — do NOT extract relationships.
Be thorough — cover every concept, mechanism, rule, and person whose ideas the document explains. A typical document should yield 15-25 entities.

## Entity Types
- Concept: Abstract ideas being explained (e.g., "Condition Variable", "Bounded Buffer")
- Method: Operations/procedures being taught (e.g., "wait()", "signal()")
- Event: Historical events relevant to understanding
- Agent: People whose IDEAS are being taught (not authors/editors)
- Claim: Rules/best practices advocated (e.g., "Always use while loops")
- Fact: Verified factual statements

## Rules
1. Only extract concepts the document is TEACHING, not just mentioning
2. Skip filenames, author names, code variable names unless they ARE the concept
3. Be thorough: extract BOTH high-level concepts AND specific mechanisms/operations
4. Include supporting concepts, not just the most prominent ones
5. Assign importance: "core" (central to learning), "supporting" (helpful context), "peripheral" (briefly mentioned)

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
  ]
}"""

# --- Two-pass: Relation extraction (Pass 2, strong model) ---
# This prompt is a TEMPLATE — {entity_list} is filled at runtime.
RELATION_PROMPT_TEMPLATE = """You are a precise relation extractor for a knowledge graph. You are given a document and a list of already-extracted entities. Your job is to identify relationships between these entities.

## Extracted Entities
{entity_list}

## Relationship Types — use ONLY one of these 10 types:
1. IsA — "A is a kind of B" (taxonomy/subtype)
2. PartOf — "A is a component/part of B" (composition)
3. Causes — "A causes B to happen" (causal)
4. Enables — "A makes B possible" or "A is necessary for B" (prerequisite)
5. Prevents — "A blocks or stops B" (inhibition)
6. Before — "A temporally precedes B" (sequence)
7. HasProperty — "A has property/attribute B" (attribution)
8. Contrasts — "A and B are opposing or alternative approaches" (comparison)
9. Supports — "A provides evidence for B" or "A reinforces B" (argumentation)
10. Attacks — "A refutes or undermines B" (argumentation)

## Critical Rules for Direction
- The SOURCE is the more specific, dependent, or acting entity
- The TARGET is the more general, independent, or receiving entity
- For PartOf: the PART is source, the WHOLE is target (e.g., wait() → Condition Variable)
- For Causes: the CAUSE is source, the EFFECT is target (e.g., Mesa Semantics → While Loop Rule)
- For Enables: the ENABLER is source, the ENABLED is target (e.g., Condition Variable → Producer/Consumer)
- For HasProperty: the THING is source, the PROPERTY is target

## Rules
1. ONLY use the entity IDs provided above. Do NOT invent new entities.
2. ONLY use the 10 relationship types listed above. If no type fits, do NOT create the relationship.
3. Think carefully about direction: read the definitions above for each type.
4. Provide brief text evidence from the document for each relationship.
5. Be thorough: aim for 15-30 relationships for a typical document.
6. Assign importance: "core" (fundamental to understanding), "supporting" (helpful context), "peripheral" (minor detail)

## Output: Return ONLY valid JSON, no markdown fences.
{
  "relationships": [
    {
      "source": "e1",
      "target": "e2",
      "type": "PartOf",
      "evidence": "brief text evidence from document",
      "importance": "core"
    }
  ]
}"""

# Backward compatibility
EXTRACTION_INSTRUCTION = CHUNK_PROMPT

# Registry for config-driven prompt selection
PROMPTS = {
    "chunk": CHUNK_PROMPT,
    "whole_doc": WHOLE_DOC_PROMPT,
    "entity_only": ENTITY_ONLY_PROMPT,
    "relation": RELATION_PROMPT_TEMPLATE,
}
