# Evaluation Report: [DOCUMENT_NAME]

## Basic Info

- **Document**: [document name]
- **Type**: [paper / textbook / article]
- **Evaluated**: [date]
- **System Version**: [version]

---

## Summary Statistics

| Metric | Ground Truth | System Output | Match |
|--------|--------------|---------------|-------|
| Total Nodes | X | Y | Z% |
| Core Nodes | X | Y | Z% |
| Total Edges | X | Y | Z% |
| Core Edges | X | Y | Z% |

---

## Node Analysis

### Correctly Extracted (✓)

| GT Node | System Node | Notes |
|---------|-------------|-------|
| concept_A | entity_001 | Exact match |

### Missing (✗)

| GT Node | Importance | Notes |
|---------|------------|-------|
| concept_B | core | Should have been extracted |

### Extra (Noise)

| System Node | Should Keep? | Notes |
|-------------|--------------|-------|
| entity_999 | No | Author name, not relevant |

---

## Edge Analysis

### Correctly Extracted (✓)

| GT Edge | System Edge | Type Match? |
|---------|-------------|-------------|
| A → B (Causes) | A → B (Causes) | ✓ |

### Missing (✗)

| GT Edge | Importance | Notes |
|---------|------------|-------|
| A → B (Causes) | core | Critical relationship missed |

### Wrong Type

| GT Edge | System Edge | Notes |
|---------|-------------|-------|
| A → B (Causes) | A → B (RelatedTo) | Type too generic |

---

## Key Issues Identified

1. **Issue 1**: Description
2. **Issue 2**: Description

---

## Recommendations

1. **Prompt Improvement**: Suggestion
2. **Pipeline Improvement**: Suggestion

---

## Overall Assessment

- **Node Quality**: [Good / Fair / Poor]
- **Edge Quality**: [Good / Fair / Poor]
- **Overall**: [Good / Fair / Poor]
