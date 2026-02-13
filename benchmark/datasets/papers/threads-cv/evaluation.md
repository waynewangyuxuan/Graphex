# Evaluation Report: threads-cv

## Basic Info

- **Document**: Chapter 30 - Condition Variables (OSTEP textbook)
- **Type**: textbook
- **Evaluated**: 2026-02-08
- **System Version**: 0.1.0

---

## Summary Statistics

| Metric | Ground Truth | System Output | Match |
|--------|--------------|---------------|-------|
| Total Nodes | 17 | 19 | - |
| Core Nodes | 8 | ~3 | **~37%** |
| Total Edges | 17 | 17 | - |
| Core Edges | 8 | ~2 | **~25%** |

---

## Node Analysis

### Correctly Extracted (✓)

| GT Node | System Node | Notes |
|---------|-------------|-------|
| Condition Variable | entity_001, entity_016 | Extracted twice (duplicate) |
| buffer | entity_005, entity_007 | Extracted twice (duplicate) |
| Mesa semantics | entity_017 | ✓ Good |
| race conditions | entity_011 | ✓ Good |
| spurious wakeup | entity_010 | Related concept, acceptable |
| signaling | entity_015 | ✓ Good |

### Missing (✗) - Critical gaps

| GT Node | Importance | Notes |
|---------|------------|-------|
| **wait()** | core | Critical operation not extracted |
| **signal()** | core | Critical operation not extracted |
| **Lock/Mutex** | core | Essential concept missing |
| **Producer/Consumer Problem** | core | Main topic of section 30.2 missing |
| **Bounded Buffer** | core | Central concept missing |
| **Hoare Semantics** | supporting | Contrast to Mesa missing |
| **Use While Loop Rule** | core | Key takeaway missing |
| **State Variable** | supporting | Important concept missing |
| **Producer Thread** | supporting | Missing |
| **Consumer Thread** | supporting | Missing |

### Extra (Noise)

| System Node | Should Keep? | Notes |
|-------------|--------------|-------|
| ARPACI-DUSSEAU (x2) | **No** | Author/copyright, not content |
| main-two-cvs-if.c | **No** | Code filename, not concept |
| main-two-cvs-while-extra-unlock.c | **No** | Code filename, not concept |
| main-two-cvs-while.c | **No** | Code filename, not concept |
| Linux man page | **No** | Reference, not core concept |
| B.W. Lampson | Maybe | Historical figure, peripheral |
| D.R. Redell | Maybe | Historical figure, peripheral |
| Tony Hoare | Maybe | Historical figure, peripheral |
| shared resource | Maybe | Generic concept |
| signal/wakeup code | **No** | Too specific/low-level |

---

## Edge Analysis

### Correctly Extracted (✓)

| GT Edge | System Edge | Type Match? |
|---------|-------------|-------------|
| Mesa semantics → signaling | rel_013 | ✗ (RelatedTo instead of HasProperty) |
| Mesa semantics → condition variables | rel_014 | ✗ (RelatedTo instead of HasProperty) |

### Missing (✗) - Critical gaps

| GT Edge | Importance | Notes |
|---------|------------|-------|
| wait() PartOf Condition Variable | core | Critical relationship |
| signal() PartOf Condition Variable | core | Critical relationship |
| Condition Variable Enables Lock | core | Key interaction |
| Bounded Buffer PartOf Producer/Consumer | core | Problem structure |
| Mesa semantics Causes Use While Loop | core | Important causation |

### Wrong Type

Almost all edges are typed as "RelatedTo" which is too generic.

| GT Type | System Type | Count |
|---------|-------------|-------|
| PartOf | RelatedTo | ~4 |
| Enables | RelatedTo | ~3 |
| Causes | RelatedTo | ~1 |
| Contrasts | RelatedTo | ~2 |
| HasProperty | RelatedTo | ~2 |

---

## Key Issues Identified

1. **Missing Core Concepts**: The two fundamental operations `wait()` and `signal()` are completely missing, even though they are explicitly defined and heavily used in the text.

2. **Extracting Filenames as Concepts**: C source filenames (main-two-cvs-if.c, etc.) are being extracted as concepts, which is noise.

3. **Duplicate Entities**: "buffer" appears twice (entity_005, entity_007), "ARPACI-DUSSEAU" appears twice. Entity resolution is failing.

4. **Author/Copyright Noise**: The copyright holder "ARPACI-DUSSEAU" is being extracted as a relevant entity.

5. **Edge Type Collapse**: Almost all relationships are "RelatedTo" instead of more specific types like PartOf, Causes, Enables.

6. **Missing Problem Structure**: The Producer/Consumer problem structure (producer, consumer, bounded buffer) is completely missing.

7. **Missing Best Practices**: Key takeaways like "use while loops" and "hold lock when signaling" are not extracted as propositions.

---

## Recommendations

### Prompt Improvements

1. **Add explicit instruction**: "Do NOT extract code filenames, author names in copyright notices, or document metadata as concepts."

2. **Prioritize definitions**: "When text explicitly defines something (e.g., 'A condition variable is...'), this MUST be extracted as a core concept."

3. **Extract methods/operations**: "When a concept has associated operations or methods (e.g., wait() and signal()), extract them as separate Method nodes."

4. **Force specific edge types**: "Avoid using 'RelatedTo'. Choose the most specific relationship type: IsA, PartOf, Causes, Enables, etc."

5. **Extract rules/best practices**: "When text states a rule or best practice (e.g., 'always use while loops'), extract it as a Proposition node."

### Pipeline Improvements

1. **Add entity deduplication**: Post-processing to merge duplicate entities.

2. **Add noise filtering**: Filter out entities that match patterns like `*.c`, `*.pdf`, copyright patterns.

3. **Add definition detection**: Use NLP to detect definitional sentences ("X is...") and ensure they're extracted.

---

## Overall Assessment

- **Node Quality**: **Poor** - Missing most core concepts, includes noise
- **Edge Quality**: **Poor** - All edges are generic RelatedTo
- **Overall**: **Poor** - System needs significant prompt and pipeline improvements

---

## Action Items

- [ ] Revise prompt to explicitly exclude filenames and author names
- [ ] Revise prompt to force extraction of explicit definitions
- [ ] Revise prompt to require specific edge types
- [ ] Add post-processing entity deduplication
- [ ] Test with revised prompt on this same document
