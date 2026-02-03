# Graphex

> AI-assisted learning canvas that externalizes knowledge as interactive graphs

## Overview

Graphex transforms knowledge consumption into a structured, active learning experience. By converting documents into interactive knowledge graphs, it addresses key cognitive challenges in reading comprehension:

- **Passive Processing**: Replaces linear reading with active graph exploration
- **Implicit Structure**: Externalizes relationships between concepts visually
- **Weak Retrieval Practice**: Integrates testing and verification of understanding
- **Cross-source Synthesis**: Enables multi-document relationship discovery

The system is grounded in cognitive science research (Kintsch's Construction-Integration Model, spreading activation theory, dual coding) and uses a multi-agent AI architecture for knowledge extraction.

## Current Phase

**MVP Core Pipeline Testing** - We are validating the core business logic:
- Node/Edge schema design
- AI extraction workflow
- Multi-agent pipeline architecture

Frontend work is explicitly deferred until core logic is proven.

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

All project documentation lives in the `Meta/` folder:

| Folder | Purpose |
|--------|---------|
| [Meta/Core/](Meta/Core/Meta.md) | Core documents (Product, Technical) |
| [Meta/Research/](Meta/Research/Meta.md) | Cognitive science research foundations |
| [Meta/Decisions/](Meta/Decisions/Meta.md) | Architecture Decision Records |
| [Meta/Milestone/](Meta/Milestone/Meta.md) | Milestone planning and tracking |

Quick links:
- [Product Requirements](Meta/Core/Product.md)
- [Technical Architecture](Meta/Core/Technical.md)
- [Node/Edge Schema](Meta/Research/Node_Edge_Schema.md)
- [Current Progress](Meta/Progress.md)
- [Change Log](CHANGELOG.md)

## Architecture

### Multi-Agent Pipeline

```
PDF → Parser → Chunker → Entity Extractor → Relation Extractor → Validator → Graph
                              ↓                    ↓                  ↓
                         Entity Registry (shared state)
```

**Core Agents (MVP)**:
1. Entity Extractor - Identifies entities per chunk
2. Relation Extractor - Finds relationships between entities
3. Validator - Checks quality, flags low-confidence results

### Node/Edge Schema

**MVP Node Types**: Concept, Event, Agent, Claim, Fact

**MVP Edge Types**: IsA, PartOf, Causes, Before, HasProperty, Supports, Attacks, RelatedTo

See [Node_Edge_Schema.md](Meta/Research/Node_Edge_Schema.md) for full definitions.

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
├── CHANGELOG.md           # Release history
├── Meta/                  # Documentation
│   ├── Core/              # Product, Technical docs
│   ├── Research/          # Cognitive science research
│   ├── Decisions/         # ADRs
│   └── Milestone/         # Milestone tracking
├── src/                   # Source code (TBD)
│   ├── pipeline/          # Pipeline orchestration
│   ├── agents/            # AI agents
│   ├── chunking/          # Document chunking
│   └── context/           # Context management
└── tests/                 # Test suite
```

### Labels
See [Meta/Labels.md](Meta/Labels.md) for issue/PR labeling conventions.

## Contributing

### Making Decisions
For architectural decisions:
1. Create an ADR in `Meta/Decisions/`
2. Use template: `Meta/Decisions/_TEMPLATE.md`
3. Update status once decided

### Tracking Progress
- Update [Progress.md](Meta/Progress.md) daily during active development
- Move completed items in [Todo.md](Meta/Todo.md) to archive
- Update milestone status when deliverables complete
