"""Test corpus definition for pipeline evaluation.

Phase 1: 10 landmark CS papers (well-structured, peer-reviewed)
Phase 2: 5 cross-discipline texts (economics, sociology, popular science, blog)
Phase 3: Multi-document groups (related papers that should cross-reference)

Each entry includes:
  - id: short identifier
  - title: human-readable title
  - url: download URL (arXiv, open-access, or direct)
  - type: paper | textbook_chapter | blog | article
  - discipline: cs | economics | sociology | biology | popular
  - expected_complexity: low | medium | high
  - notes: what makes this a good test case
"""

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 1: CS PAPERS
# ═══════════════════════════════════════════════════════════════════════════

PHASE1_CS_PAPERS = [
    {
        "id": "attention",
        "title": "Attention Is All You Need",
        "url": "https://arxiv.org/pdf/1706.03762",
        "type": "paper",
        "discipline": "cs",
        "expected_complexity": "high",
        "notes": "Dense architecture paper. Tests: mechanism extraction, "
                 "nested sub-components (multi-head attention, positional encoding), "
                 "comparison narrative (vs RNNs/CNNs).",
    },
    {
        "id": "resnet",
        "title": "Deep Residual Learning for Image Recognition",
        "url": "https://arxiv.org/pdf/1512.03385",
        "type": "paper",
        "discipline": "cs",
        "expected_complexity": "medium",
        "notes": "Clear problem→solution arc. Tests: problem-mechanism-result "
                 "narrative, experiment discussion as branches.",
    },
    {
        "id": "gan",
        "title": "Generative Adversarial Networks",
        "url": "https://arxiv.org/pdf/1406.2661",
        "type": "paper",
        "discipline": "cs",
        "expected_complexity": "medium",
        "notes": "Two competing mechanisms (generator/discriminator). "
                 "Tests: dual-track narrative, game-theoretic framing.",
    },
    {
        "id": "bert",
        "title": "BERT: Pre-training of Deep Bidirectional Transformers",
        "url": "https://arxiv.org/pdf/1810.04805",
        "type": "paper",
        "discipline": "cs",
        "expected_complexity": "high",
        "notes": "Builds on prior work heavily (ELMo, GPT, Transformer). "
                 "Tests: background/context handling, comparison segments.",
    },
    {
        "id": "dropout",
        "title": "Dropout: A Simple Way to Prevent Neural Networks from Overfitting",
        "url": "https://jmlr.org/papers/volume15/srivastava14a/srivastava14a.pdf",
        "type": "paper",
        "discipline": "cs",
        "expected_complexity": "medium",
        "notes": "Technique paper with strong intuition→math→experiments arc. "
                 "Tests: motivation narrative, biological analogy as branch.",
    },
    {
        "id": "mapreduce",
        "title": "MapReduce: Simplified Data Processing on Large Clusters",
        "url": "https://static.googleusercontent.com/media/research.google.com/en//archive/mapreduce-osdi04.pdf",
        "type": "paper",
        "discipline": "cs",
        "expected_complexity": "medium",
        "notes": "Systems paper. Tests: API design narrative, "
                 "implementation details as deep branches, real-world examples.",
    },
    {
        "id": "bitcoin",
        "title": "Bitcoin: A Peer-to-Peer Electronic Cash System",
        "url": "https://bitcoin.org/bitcoin.pdf",
        "type": "paper",
        "discipline": "cs",
        "expected_complexity": "low",
        "notes": "Short (9 pages), clear narrative. Good baseline test. "
                 "Tests: problem-solution structure, mechanism chain.",
    },
    {
        "id": "raft",
        "title": "In Search of an Understandable Consensus Algorithm (Raft)",
        "url": "https://raft.github.io/raft.pdf",
        "type": "paper",
        "discipline": "cs",
        "expected_complexity": "high",
        "notes": "Explicitly designed for understandability. "
                 "Tests: decomposition narrative, sub-problem tree structure.",
    },
    {
        "id": "batchnorm",
        "title": "Batch Normalization: Accelerating Deep Network Training",
        "url": "https://arxiv.org/pdf/1502.03167",
        "type": "paper",
        "discipline": "cs",
        "expected_complexity": "medium",
        "notes": "Problem diagnosis → technique → results. "
                 "Tests: internal covariate shift as motivation branch.",
    },
    {
        "id": "adam",
        "title": "Adam: A Method for Stochastic Optimization",
        "url": "https://arxiv.org/pdf/1412.6980",
        "type": "paper",
        "discipline": "cs",
        "expected_complexity": "medium",
        "notes": "Optimizer paper combining two ideas (momentum + RMSProp). "
                 "Tests: synthesis narrative, algorithm walkthrough as mechanism.",
    },
]


# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2: CROSS-DISCIPLINE
# ═══════════════════════════════════════════════════════════════════════════

PHASE2_CROSS_DISCIPLINE = [
    {
        "id": "econ-nash",
        "title": "Non-Cooperative Games (Nash, 1951)",
        "url": "https://www.jstor.org/stable/1969529",
        "alt_source": "Provide PDF manually — JSTOR requires access",
        "type": "paper",
        "discipline": "economics",
        "expected_complexity": "high",
        "notes": "Mathematical economics. Tests: theorem-proof structure, "
                 "definition→lemma→theorem narrative arc.",
    },
    {
        "id": "sociology-granovetter",
        "title": "The Strength of Weak Ties (Granovetter, 1973)",
        "url": "https://sociology.stanford.edu/sites/g/files/sbiybj9501/f/publications/the_strength_of_weak_ties_and_exch_am_j_soc_copy.pdf",
        "type": "paper",
        "discipline": "sociology",
        "expected_complexity": "medium",
        "notes": "Qualitative + quantitative sociology. Tests: argument-evidence "
                 "structure, empirical findings as branches.",
    },
    {
        "id": "bio-crispr",
        "title": "A Programmable Dual-RNA-Guided DNA Endonuclease (Doudna & Charpentier)",
        "url": "https://www.science.org/doi/pdf/10.1126/science.1225829",
        "alt_source": "Provide PDF manually — Science requires access",
        "type": "paper",
        "discipline": "biology",
        "expected_complexity": "high",
        "notes": "Wet lab biology. Tests: experimental narrative (method→result→implication), "
                 "figure-heavy content handling.",
    },
    {
        "id": "popular-thinking-fast",
        "title": "Thinking, Fast and Slow — Chapter 1 excerpt",
        "alt_source": "Provide text/PDF manually — copyrighted book",
        "type": "book_chapter",
        "discipline": "psychology",
        "expected_complexity": "low",
        "notes": "Popular science writing. Tests: storytelling structure, "
                 "anecdote→concept pattern, very different from academic style.",
    },
    {
        "id": "blog-scaling",
        "title": "Scaling Laws for Neural Language Models (Kaplan et al.)",
        "url": "https://arxiv.org/pdf/2001.08361",
        "type": "paper",
        "discipline": "cs",
        "expected_complexity": "medium",
        "notes": "Empirical paper, lots of graphs and findings. "
                 "Tests: data-driven narrative, finding→implication branches.",
    },
]


# ═══════════════════════════════════════════════════════════════════════════
# PHASE 3: MULTI-DOCUMENT GROUPS
# ═══════════════════════════════════════════════════════════════════════════

PHASE3_MULTI_DOCUMENT = [
    {
        "group_id": "transformer-evolution",
        "title": "Transformer Architecture Evolution",
        "doc_ids": ["attention", "bert"],
        "expected_cross_relations": [
            "BERT builds on Transformer architecture",
            "Both use self-attention mechanism",
            "BERT modifies training objective (MLM vs autoregressive)",
            "Positional encoding shared concept",
        ],
        "notes": "Tests: shared concept linking, temporal evolution narrative.",
    },
    {
        "group_id": "training-techniques",
        "title": "Neural Network Training Techniques",
        "doc_ids": ["dropout", "batchnorm", "adam"],
        "expected_cross_relations": [
            "All address training difficulty",
            "Dropout and BatchNorm both regularize but differently",
            "Adam optimizes gradient descent that all techniques improve",
            "BatchNorm and Dropout can be combined",
        ],
        "notes": "Tests: complementary techniques, shared problem space.",
    },
    {
        "group_id": "distributed-systems",
        "title": "Distributed Systems Foundations",
        "doc_ids": ["mapreduce", "raft", "bitcoin"],
        "expected_cross_relations": [
            "All handle distributed coordination",
            "Raft and Bitcoin both solve consensus (different threat models)",
            "MapReduce assumes trusted nodes, Bitcoin assumes adversarial",
            "Fault tolerance as shared concern",
        ],
        "notes": "Tests: same domain, different sub-problems, concept overlap.",
    },
]


# ═══════════════════════════════════════════════════════════════════════════
# ALL DOCUMENTS
# ═══════════════════════════════════════════════════════════════════════════

ALL_SINGLE_DOCS = PHASE1_CS_PAPERS + PHASE2_CROSS_DISCIPLINE

ALL_DOCS_BY_ID = {d["id"]: d for d in ALL_SINGLE_DOCS}
