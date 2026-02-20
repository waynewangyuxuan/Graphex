# Entity Extraction — Evidence

## KGGen (NeurIPS'25, Stanford)
**Repo**: https://github.com/stair-lab/kg-gen (MIT License)
**Paper**: https://arxiv.org/abs/2502.09956

### Two-Pass Extraction
- `src/kg_gen/steps/_1_get_entities.py` — Entity extraction pass
  - DSPy `TextEntities` Signature: "Extract key entities... be THOROUGH"
  - LiteLLM path: structured JSON output with `EntitiesResponse` schema
  - Returns: `list[str]` (just entity names, no definitions)

- `src/kg_gen/steps/_2_get_relations.py` — Relation extraction pass
  - `_create_relations_model(entities)` (L79-98): dynamically creates `Literal[tuple(entities)]` type
  - This means subject/object fields are TYPE-CONSTRAINED to only use entity names from Pass 1
  - `parse_relations_response()` (L9-70): graceful fallback with entity set filtering
  - `FixedRelations` chain-of-thought (L269-281): when strict typing fails, uses CoT to fix relations

### Prompts
- `src/kg_gen/prompts/entities.txt` — Key rules:
  - "Focus on substantive mentions" (L19)
  - "Prioritize entities with relationship potential" (L22)
  - "Be selective rather than inclusive" (L32) — explicit anti-noise guidance
  - "Avoid overly generic terms" (L25)
  - "Normalize entity names" (L29) — canonical form selection

- `src/kg_gen/prompts/relations.txt` — Key rules:
  - "Subject and object must be from entities list" (L3-5)
  - "Avoid vague predicates like related_to" (L20)
  - Includes systematic process: map entities to text → identify relationships → draft triples → check isolated entities → finalize (L33-51)

### Chunked Processing
- `src/kg_gen/kg_gen.py` L254-267: when chunk_size set, uses `ThreadPoolExecutor` for parallel per-chunk extraction, then `set()` union for entities/relations
- Default: no chunking (tries whole document first, falls back to chunking on context length error)

### Deduplication
- `src/kg_gen/steps/_3_deduplicate.py`: Three methods — SemHash, LM-based, Full (both)
- `src/kg_gen/utils/llm_deduplicate.py`: KMeans clustering (128 per cluster) → intra-cluster LLM dedup with BM25+embedding rank fusion retrieval

## sift-kg
**Repo**: https://github.com/juanceresa/sift-kg (MIT License)

### Document-Level Context
- `src/sift_kg/extract/extractor.py` L72-89: `_generate_doc_context()`
  - "Summarize this document excerpt in 2-3 sentences"
  - "Focus on: what type of document this is, who the key participants are, what the main subject matter is"
  - Called ONCE per document using first chunk
  - Result injected into every chunk's prompt

### Context Injection
- `src/sift_kg/extract/prompts.py` L129-134 in `build_combined_prompt()`:
  ```
  DOCUMENT CONTEXT (applies to entire document, not just this excerpt):
  {doc_context}
  ```

### Domain-Driven Extraction
- `src/sift_kg/extract/prompts.py` L12-77: `build_entity_prompt()`
  - Entity types from `DomainConfig` with descriptions + extraction_hints
  - `canonical_names` support: "ALLOWED VALUES (use ONLY these exact names)"
  - Confidence scoring per entity (0.0-1.0)
  - Context quote extraction for evidence

### Combined Prompt
- `src/sift_kg/extract/prompts.py` L80-190: `build_combined_prompt()`
  - Single call for entities + relations (our current approach)
  - Includes relation direction hints: `source_types → target_types`
  - "Do not infer relationships from co-occurrence alone" (L183)

### Post-merge Dedup
- `src/sift_kg/extract/extractor.py` L259-284: `_dedupe_entities()`
  - Key: `name.lower().strip()` + entity_type as dedup key
  - Keeps highest confidence entry
  - Merges all unique context quotes with " ||| " separator

## Graphiti (Zep)
**Repo**: https://github.com/getzep/graphiti (Apache 2.0)

### Multi-Phase Extraction
- `graphiti_core/graphiti.py` L929-975: add_episode pipeline
  1. `extract_nodes()` — entity names + types only
  2. `resolve_extracted_nodes()` — cascading ER (see graphiti-er-module)
  3. `extract_edges()` — relationships between resolved entities
  4. `extract_attributes_from_nodes()` — summaries, AFTER resolution, with only new edges

### Extraction Prompts
- `graphiti_core/prompts/extract_nodes.py` L158-186: `extract_text()`
  - "Extract significant entities, concepts, or actors"
  - "Avoid creating nodes for relationships or actions"
  - "Be as explicit as possible in naming"
  - Classification via `entity_type_id` (not free-form type strings)
  - Supports `custom_extraction_instructions` injection

### Summary as Separate Step
- `graphiti_core/prompts/extract_nodes.py` L250-274: `extract_summary()`
  - "Update the summary that combines relevant information from MESSAGES and existing summary"
  - Runs AFTER entity resolution
  - Only processes new edges (avoids duplicating existing facts)
  - Max character limit enforced

## Microsoft GraphRAG
**Paper**: https://arxiv.org/html/2404.16130v1

### Key Design Decisions (from paper/docs, not from code):
- Chunk size 600 tokens extracts ~2x more entity references than 2400 tokens
- Entity types are configurable (default: Geo, Person, Event, Organization)
- Post-extraction: group by title+type → LLM summarizes all descriptions into one
- Multipart prompt: entities first (name, type, description), then relationships
- Few-shot examples are the primary domain customization mechanism
