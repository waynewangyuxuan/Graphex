# Graphex

> AI-assisted learning canvas that externalizes knowledge as interactive graphs

## Overview

Graphex transforms knowledge consumption into a structured, active learning experience. By converting documents into interactive knowledge graphs, it addresses key cognitive challenges in reading comprehension:

- **Passive Processing**: Replaces linear reading with active graph exploration
- **Implicit Structure**: Externalizes relationships between concepts visually
- **Weak Retrieval Practice**: Integrates testing and verification of understanding
- **Cross-source Synthesis**: Enables multi-document relationship discovery

The system is grounded in cognitive science research (Kintsch's Construction-Integration Model, spreading activation theory, dual coding) and uses an LLM-based narrative extraction pipeline.

## Current Phase

**Pipeline Refinement + Frontend Planning** - The core extraction pipeline is proven and working end-to-end. Current focus:
- Refining extraction quality (anchor resolution, spine/branch ratio)
- Evaluation suite for measuring pipeline accuracy across papers
- Planning frontend interactive graph/tree views

## Quick Start

```bash
# Clone the repository
git clone <repo-url>
cd Graphex

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest
```

## Documentation

All project documentation lives in the `META/` folder:

| Folder | Purpose |
|--------|---------|
| [META/Core/](META/Core/Meta.md) | Core documents (Product, Technical) |
| [META/Research/](META/Research/Meta.md) | Cognitive science research foundations |
| [META/Decisions/](META/Decisions/Meta.md) | Architecture Decision Records |
| [META/Milestone/](META/Milestone/Meta.md) | Milestone planning and tracking |

Quick links:
- [Product Requirements](META/Core/Product.md)
- [Technical Architecture](META/Core/Technical.md)
- [Narrative Schema](META/Research/Narrative_Schema.md)
- [Current Progress](META/Progress.md)

## Architecture

### Extraction Pipeline

```
PDF → PyMuPDF Parser → _preprocess_pdf_text() → Adaptive Chunker → Narrative Extractor (LLM) → Review Pass → Anchor Resolver → Graph-to-Tree
```

**Key Components**:
1. **PDF Parser** (`src/parsing/pdf_parser.py`) -- PyMuPDF-based, with marker-pdf as optional GPU backend
2. **Adaptive Chunker** (`src/chunking/programmatic_chunker.py`) -- Logarithmic chunk scaling based on document size
3. **Narrative Extractor** (`src/extraction/narrative_extractor.py`) -- Single-pass LLM extraction producing segments + relations per chunk, with JSON salvage + retry
4. **Anchor Resolver** (`src/binding/anchor_resolver.py`) -- 7-level cascade (exact to embedding fallback) for text-graph binding
5. **Graph-to-Tree** (`src/transform/graph_to_tree.py`) -- LLM-based graph to hierarchical spine tree with structural constraints

### Narrative Segment Schema

The pipeline produces narrative segments (not entity-relation triples). Each segment has:
- `id`, `type` (mechanism, context, evidence, etc.), `title`, `content`
- `anchor` (verbatim text span for text-graph binding)
- `concepts` (tagged with role: introduces/develops/applies)
- `relations` (typed connections between segments)

## Development Workflow

### Branching Strategy
- `main` - Production-ready code
- `develop` - Integration branch
- `feat/*` - Feature branches
- `fix/*` - Bug fix branches

### Commit Messages
Follow [Conventional Commits](https://www.conventionalcommits.org/):
```
type(scope): description

[optional body]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

### Code Review Checklist
- [ ] Code follows project conventions
- [ ] Tests pass and coverage maintained
- [ ] Documentation updated
- [ ] No security issues introduced

## Project Conventions

### File Structure
```
Graphex/
├── CLAUDE.md              # This file
├── META/                  # Documentation (includes Progress.md)
│   ├── Core/              # Product, Technical docs
│   ├── Research/          # Cognitive science research
│   ├── Decisions/         # ADRs
│   └── Milestone/         # Milestone tracking
├── src/                   # Source code
│   ├── parsing/           # PDF parsing (pdf_parser.py, marker_parser.py)
│   ├── chunking/          # Adaptive chunking (programmatic_chunker.py)
│   ├── extraction/        # Narrative extraction (narrative_extractor.py, narrative_prompts.py)
│   ├── binding/           # Anchor resolution (anchor_resolver.py)
│   ├── transform/         # Graph-to-tree (graph_to_tree.py)
│   └── resolution/        # Entity resolution (entity_resolver.py, parallel_merge.py)
├── experiments/           # Experiment infrastructure
│   ├── eval/              # Evaluation suite (run_eval.py, test_corpus.py, audit_anchor_quality.py)
│   ├── runners/           # Experiment runners
│   ├── configs/           # Experiment configs
│   └── results/           # Output results
└── tests/                 # Test suite
```

### Labels
See [META/Labels.md](META/Labels.md) for issue/PR labeling conventions.

## Contributing

### Making Decisions
For architectural decisions:
1. Create an ADR in `META/Decisions/`
2. Use template: `META/Decisions/_TEMPLATE.md`
3. Update status once decided

### Tracking Progress
- Update [Progress.md](META/Progress.md) daily during active development
- Move completed items in [Todo.md](META/Todo.md) to archive
- Update milestone status when deliverables complete
