# Anchor Resolution Quality Audit

Batchnorm paper audit (2026-03-07). Findings drove the verbatim anchor enforcement and embedding fallback improvements.

## Results (Pre-Fix Baseline)

| Match Type | Count | Correct | Accuracy |
|-----------|-------|---------|----------|
| Text-Fuzzy (conf >= 0.75) | 5 | 4 | 80.0% |
| Embedding (conf < 0.75) | 21 | 8 | 38.1% |
| **Total** | **26** | **12** | **46.2%** |

## Root Causes Identified

### 1. LLM Anchor Paraphrasing (15% of segments)

The extraction LLM was generating "semantic anchors" instead of verbatim quotes. Example:

- **s5**: Extracted "We define Internal Covariate Shift as..." — phrase doesn't exist in PDF at all
- **s6**: Opening phrase matches but conclusion completely rewritten (math paraphrased)

**Fix applied**: Strict verbatim rules + self-check step in extraction prompt (8-20 words, character-for-character).

### 2. PDF Line-Break Artifacts (11.5% of segments)

PDF text has hyphenated line breaks (`continu-\nously`) that cause exact match to fail. Example:

- **s3**: "...continuously adapt" in anchor vs `continu-\nously adapt` in PDF
- Should have resolved via normalized whitespace but fell through to embedding

**Fix applied**: `_normalize_pdf_breaks()` in resolver + dehyphenation in `_preprocess_pdf_text()`.

### 3. Embedding Over-Matching (27% of segments)

Embedding fallback matched semantically similar but positionally wrong sentences:

- **s2**: Anchor about "SGD has proved effective" matched a different SGD discussion at position 17423
- No confidence-accuracy correlation (conf=0.7 was often wrong, conf=0.55 was often right)

**Fix applied**: Removed `_try_prefix_words` (3-word match, 81% false positive); tightened `_try_normalized` to 8-word minimum.

### 4. Pipeline Data Inconsistency (discovered 2026-03-08)

Root cause of 0% exact match after verbatim prompt fix:

- Chunks contained raw PDF artifacts (`activa- tion`)
- LLM faithfully copied verbatim from chunks (correct behavior)
- Resolver received cleaned full text (`activation`)
- Result: anchor and full text never matched exactly

**Fix applied**: Dehyphenation + single newline collapse in `_preprocess_pdf_text()`, applied before chunking.

## Post-Fix Result

After all fixes: batchnorm **0 exact → 26 exact**, embedding **21 → 0**, failed **0**.

## Failure Pattern Summary

| Pattern | Count | Confidence | Root Cause |
|---------|-------|-----------|------------|
| Hallucinated (not in PDF) | 4 | 0.54-0.80 | LLM extraction |
| PDF line breaks | 3 | 0.67-0.69 | Text formatting |
| Wrong context (embedding) | 7 | 0.54-0.70 | Embedding over-match |

## Key Takeaway

When anchors are verbatim and text is normalized consistently, text-based matching works at ~100%. Embedding fallback is a safety net, not a primary strategy. The real fix was ensuring data consistency across the pipeline (preprocess before chunk, not after).
