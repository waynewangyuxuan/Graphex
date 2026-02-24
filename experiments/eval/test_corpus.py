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
        "id": "econ-lemons",
        "title": "The Market for Lemons: Quality Uncertainty and the Market Mechanism (Akerlof, 1970)",
        "url": "https://personal.utdallas.edu/~nina.baranchuk/Fin7310/papers/Akerlof1970.pdf",
        "alt_urls": [
            "https://www.sfu.ca/~wainwrig/Econ400/akerlof.pdf",
        ],
        "type": "paper",
        "discipline": "economics",
        "expected_complexity": "medium",
        "notes": "Information asymmetry classic (Nobel Prize basis). Tests: "
                 "informal argumentation, real-world analogy (used cars) as mechanism, "
                 "multi-market application pattern.",
    },
    {
        "id": "sociology-granovetter",
        "title": "The Strength of Weak Ties (Granovetter, 1973)",
        "url": "https://www.cs.cmu.edu/~jure/pub/papers/granovetter73ties.pdf",
        "alt_urls": [
            "https://snap.stanford.edu/class/cs224w-readings/granovetter73weakties.pdf",
        ],
        "type": "paper",
        "discipline": "sociology",
        "expected_complexity": "medium",
        "notes": "Qualitative + quantitative sociology. Tests: argument-evidence "
                 "structure, empirical findings as branches.",
    },
    {
        "id": "bio-alphafold",
        "title": "Highly Accurate Protein Structure Prediction with AlphaFold (Jumper et al., 2021)",
        "url": "https://www.nature.com/articles/s41586-021-03819-2.pdf",
        "alt_urls": [
            "https://www.nature.com/articles/s41586-021-03819-2",
        ],
        "type": "paper",
        "discipline": "biology",
        "expected_complexity": "high",
        "notes": "Biology+AI crossover (Nobel Prize). Tests: complex architecture "
                 "narrative, experimental validation against CASP14, dense methodology.",
    },
    {
        "id": "psych-prospect",
        "title": "Prospect Theory: An Analysis of Decision under Risk (Kahneman & Tversky, 1979)",
        "url": "https://web.mit.edu/curhan/www/docs/Articles/15341_Readings/Behavioral_Decision_Theory/Kahneman_Tversky_1979_Prospect_theory.pdf",
        "alt_urls": [
            "https://courses.washington.edu/pbafhall/514/514%20Readings/ProspectTheory.pdf",
        ],
        "type": "paper",
        "discipline": "psychology",
        "expected_complexity": "high",
        "notes": "Behavioral economics foundation (Nobel Prize). Tests: "
                 "empirical observation→formal theory arc, value function + "
                 "weighting function as dual mechanisms, critique of expected utility.",
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
