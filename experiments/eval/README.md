# Pipeline Evaluation Suite

## Overview

Three-phase validation of the narrative extraction pipeline before product readiness.

### Phase 1: CS Papers (10 papers)
Validate core extraction quality on well-structured technical content.

### Phase 2: Cross-Discipline (5+ texts)
Validate generalization beyond CS — economics, sociology, popular articles.

### Phase 3: Multi-Document
Validate cross-document relation building between related texts.

## Running

```bash
# Phase 1 & 2: Single-document evaluation
python experiments/eval/run_eval.py --phase 1
python experiments/eval/run_eval.py --phase 2

# Phase 3: Multi-document evaluation
python experiments/eval/run_eval.py --phase 3

# Score a completed run
python experiments/eval/score.py experiments/eval/results/
```
