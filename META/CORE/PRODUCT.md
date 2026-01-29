# Motivation

Information consumption is evolving beyond traditional linear reading. AI enables knowledge to be **dynamic** (expand, summarize, and generate examples on demand), **flexible** (reveal inter-relationships across multiple sources), and **accessible** (restructure content to match individual learning needs).

For knowledge-oriented reading—as opposed to literary or aesthetic reading—AI can transform the consumption process into a structured, active learning experience. Rather than replacing reading, AI can scaffold deeper comprehension and synthesis.

# Problem

Current knowledge consumption methods face several cognitive challenges:

1. **Passive Processing**: Reading linearly encourages shallow, fluency-based processing that creates an illusion of understanding without true comprehension
2. **Implicit Structure**: The relationships between concepts remain hidden in prose, requiring readers to mentally construct knowledge networks without support
3. **Weak Retrieval Practice**: Most readers do not test their understanding, missing the powerful testing effect that strengthens long-term retention
4. **Isolated Sources**: Reading documents independently makes cross-source synthesis difficult, limiting knowledge transfer and abstraction of general principles
5. **No Metacognitive Feedback**: Readers lack insight into what they truly understand versus what merely feels familiar
6. **Forgetting Without Reinforcement**: Knowledge decays over time without spaced retrieval practice

# Solution

An AI-assisted learning canvas that externalizes knowledge as interactive graphs, requiring active engagement while providing structured support. The system balances desirable difficulties (user must read, generate explanations, synthesize) with intelligent scaffolding (AI reveals structure, provides verification, schedules review).

**Core Learning Cycle**:
1. AI generates graph representations from documents (full or skeleton options)
2. User reads original content using graph as navigation structure
3. User adds notes, generates explanations, and refines graph structure
4. System tests understanding through targeted challenges
5. Scheduled spaced repetition reinforces long-term retention
6. Iterate with increasing complexity and cross-document synthesis

# Product

## Feature 1: Adaptive Graph Generation

**Description**: Upload documents or links to generate knowledge graphs using Mermaid, with user choice between full AI-generated graphs and skeleton graphs for completion.

**Implementation**:
- **Nodes**: Represent core concepts/arguments with summarized titles
- **Edges**: Directed connections showing relationships between concepts
- **Progressive Disclosure**: Start with high-level graph (5-7 main nodes), allow users to expand nodes into sub-graphs to manage cognitive load
- **Complexity Indicators**: Visual cues showing dense vs. sparse regions to help users pace learning
- **Default**: Skeleton graph (user completes structure) with option to reveal full AI graph for scaffolding

**Cognitive Rationale**: Mirrors semantic memory's network structure (Collins & Quillian, 1969). Skeleton option leverages generation effect (Slamecka & Graf, 1978)—self-generated structures remembered 2-3x better. Full graph option provides scaffolding for novices (expertise reversal effect).

## Feature 2: Integrated Reading Interface

**Description**: Side panel displays source documents with automatic navigation to relevant passages when nodes are clicked.

**Implementation**:
- Click node → side panel highlights corresponding passage in original text
- Show surrounding context (paragraph before/after) to maintain narrative flow
- Breadcrumb trail: Document → Section → Specific passage
- Keep graph visible while reading to prevent split-attention effect
- Smooth transitions with visual connection (animation from node to text)

**Cognitive Rationale**: Prevents split-attention effect (Sweller et al., 1998). Maintains encoding specificity—context at encoding matches retrieval context. Supports dual coding (Paivio, 1971) by linking visual graph to verbal content.

## Feature 3: Relationship Types and Bidirectional Connections

**Description**: Multiple types of relationships between nodes, both directed and bidirectional.

**Implementation**:
- **Directed Relationships**: Causation (A→B), temporal sequence, prerequisites, derivation
- **Bidirectional Relationships**: Similarity, mutual influence, part-whole, synonymy
- **Typed Edges**: Label connections as "supports," "contradicts," "exemplifies," "defines," "applies"
- **Visual Differentiation**: Different colors/styles for relationship types
- **Connection Notes**: Users and AI can annotate why relationships exist (not just what they are)

**Cognitive Rationale**: Matches how semantic memory actually operates—not all relationships are directional (Anderson, 1983). Explicit relationship types facilitate structure-mapping for analogical reasoning (Gentner, 1983). Connection annotations force relational processing, a key predictor of retention.

## Feature 4: Enhanced Note-Taking System

**Description**: Structured note-taking on both nodes and connections with organization and management features.

**Implementation**:
- **Node Notes**: Main claims, evidence, personal questions, connections to prior knowledge
- **Connection Notes**: Why relationship exists, strength of evidence, user's interpretation
- **Note Templates**: Guided prompts—"Main claim:", "Evidence:", "How this connects to [other concept]:", "My question:"
- **Anti-Verbatim Safeguards**: 
  - Character limits forcing summarization
  - Disable copy-paste from source documents
  - Prompts requiring "in your own words"
- **Note Organization**:
  - Tagging system across nodes and connections
  - Note linking (reference notes from other nodes)
  - Search/filter by note content
  - Visual indicators showing which nodes have notes
- **Export**: Preserve graph structure + notes as nested markdown or PDF

**Cognitive Rationale**: Organizational note-taking (not verbatim) drives retention (Mueller & Oppenheimer, 2014). Templates reduce working memory load (Cowan, 2001). Forced summarization ensures generative processing (Fiorella & Mayer, 2016). Note linking creates second-order knowledge network.

## Feature 5: Pre-Explanation Retrieval

**Description**: Before revealing AI's explanation of any connection, require user to generate their own hypothesis.

**Implementation**:
- User clicks connection between nodes
- System prompts: "What do you think this relationship is? Why are these concepts connected?"
- User types hypothesis (minimum 20 words)
- AI then reveals: 
  - Original text supporting the connection
  - AI's explanation of relationship
  - Evaluation of user's hypothesis ("You identified X correctly, but consider Y...")
- User then must self-explain in their own words before proceeding

**Cognitive Rationale**: Pretesting effect (Kornell et al., 2009)—attempting answer before seeing it improves retention 30%, even when wrong. Prevents fluency illusion (Kornell & Bjork, 2008) where AI explanations feel "easy" and create false confidence. Self-explanation after AI explanation doubles learning (Chi et al., 1994).

## Feature 6: Multi-Document Synthesis

**Description**: Work with multiple documents simultaneously, revealing cross-source patterns, agreements, and contradictions.

**Implementation**:
- **Multi-Source Graph View**:
  - Color-code nodes by source document
  - Visual highlighting of conceptual intersections
  - Mark convergent connections (multiple sources support same claim)
  - Mark divergent connections (sources disagree)
- **Explicit Conflict Identification**: AI flags "Paper A argues X, Paper B argues Y—contradiction on [specific point]"
- **Gap Analysis**: AI identifies what one source discusses but another ignores
- **Synthesis Challenges**:
  - "Compare how these three authors define [concept]"
  - "Map causal chain across sources: A establishes X→Y, B shows Y→Z"
  - "What general principle emerges from all sources?"
- **Cross-Reference Notes**: Notes can reference concepts from multiple documents
- **Source Comparison Table**: Side-by-side view of how different sources address same concept

**Cognitive Rationale**: Schema induction through comparison (Gick & Holyoak, 1983)—two examples with comparison prompts yield 80% transfer vs. 20% from single example. Essential for transfer of learning (Barnett & Ceci, 2002). Interleaving multiple sources improves discrimination and retention (Rohrer & Taylor, 2007).

## Feature 7: Comprehension Verification System

**Description**: Adaptive testing that challenges understanding of sub-graphs and cross-document synthesis.

**Implementation**:
- **Challenge Types**:
  - Explain sub-graph without looking at notes
  - Predict missing connections
  - Identify contradictions across sources
  - Apply concepts to novel scenarios
  - Reconstruct graph from memory
- **Adaptive Difficulty**: Harder questions as user demonstrates mastery
- **Immediate Feedback**: Explanation of correct answers, addressing misconceptions
- **Mastery Criteria**: Clear thresholds (e.g., 90% accuracy on sub-graph questions)
- **Visual Progress**: Show which graph regions are "mastered" vs. need review

**Cognitive Rationale**: Testing effect (Roediger & Karpicke, 2006)—testing yields 60% retention vs. 40% for re-reading after one week. Transfer-appropriate processing (Morris et al., 1977)—testing with graphs matches learning with graphs. Metacognitive monitoring (Metcalfe & Kornell, 2005) helps users calibrate their understanding.

## Feature 8: Spaced Repetition System

**Description**: Scheduled re-testing of understanding at increasing intervals to combat forgetting curve.

**Implementation**:
- **Automatic Scheduling**: Based on user's performance and retention goals
  - 1-week retention: Re-test after 12-24 hours
  - 1-month retention: Re-test after 1 week
  - 1-year retention: Re-test after 3-4 weeks
- **Review Notifications**: "Time to review [concept] from [document]"
- **Adaptive Intervals**: Increase spacing for mastered content, decrease for struggling areas
- **Review Modes**:
  - Quick quiz on specific nodes
  - Reconstruct portion of graph
  - Explain connections in own words
- **Long-Term Dashboard**: Track retention over weeks/months

**Cognitive Rationale**: Spacing effect (Cepeda et al., 2006)—distributed practice vastly superior to massed practice. Without spacing, you get only ~50% of potential retention benefit. Optimal intervals depend on desired retention period.

## Feature 9: Metacognitive Scaffolding

**Description**: Features that help users monitor and regulate their own learning.

**Implementation**:
- **Confidence Ratings**: After interacting with each node—"How well do you understand this?" (1-5 scale)
- **Visual Understanding Map**: Nodes colored by confidence level (red=struggling, green=confident)
- **Calibration Feedback**: Compare confidence ratings to test performance—"You rated yourself 5/5 but scored 60% on questions"
- **Reflection Prompts**:
  - "What surprised you about this connection?"
  - "How does this relate to what you already knew?"
  - "What's still unclear?"
- **Learning Strategy Suggestions**: Based on performance patterns—"You're struggling with cross-document synthesis. Try comparing sources side-by-side."
- **Session Summaries**: "Today you mastered 5 concepts, need to review 3, and added 12 connections"

**Cognitive Rationale**: Self-regulated learning cycle (Zimmerman, 2002)—forethought, performance, self-reflection. Metacognitive monitoring is what separates expert from novice learners. Calibration training helps users develop accurate judgment of learning (Metcalfe & Kornell, 2005).

## Feature 10: User Graph Customization

**Description**: Users can rearrange, create, and remove nodes and connections to personalize their knowledge structure.

**Implementation**:
- **Rearrangement**: Drag-and-drop nodes, re-route connections
- **Justification Required**: "Why does this connection make sense?" before creating new edge
- **Semantic Suggestions**: AI recommends placements based on content similarity—"Based on content, Node X might connect better to Node Y"
- **Version History**: Save different graph layouts, compare approaches
- **Guided vs. Free Mode**:
  - Beginners: Use AI graph first, customize after initial comprehension
  - Advanced: Start with skeleton and build
- **Share Graphs**: Export and share custom graphs with study partners
- **Alternative Graphs**: View how other users structured same content (optional, anonymized)

**Cognitive Rationale**: Cognitive flexibility from multiple representations (Spiro et al., 1988). Self-organization leverages generation effect. BUT expertise reversal effect (Kalyuga et al., 2003) means novices need guidance first. Justification requirements prevent shallow, aesthetic-based reorganization. Seeing alternative structures promotes flexible understanding.

## Feature 11: Prior Knowledge Activation

**Description**: Before showing AI-generated graph, prompt users to activate existing knowledge schemas.

**Implementation**:
- **Pre-Reading Prompt**: "Before we analyze this document, what do you already know about [main topic]?"
- **Free-Form Brain Dump**: Users write or sketch existing knowledge
- **Concept Inventory**: Checklist of related concepts—"Check which terms you're familiar with"
- **Initial Graph**: Users create their own provisional graph before seeing AI's
- **Integration View**: After reading, compare user's initial graph to AI's graph—highlight gaps and overlaps

**Cognitive Rationale**: Prior knowledge activation primes relevant schemas, creating "hooks" for new information. Schema theory (Rumelhart, 1980) shows existing structures determine what's encoded. Revealing gaps between prior knowledge and new content drives motivated learning.

## Feature 12: Collaborative Learning Features

**Description**: Social elements that leverage peer learning effects.

**Implementation**:
- **Share Graphs**: Send graph + notes to study partners
- **Collaborative Annotation**: Multiple users add notes to shared graph
- **Comparison Mode**: View how peer structured same content—"Alex emphasized causal relationships, you emphasized examples"
- **Peer Challenges**: Users can create verification questions for each other
- **Explain-to-Partner**: Prompt users to "explain this sub-graph to someone else" (can record or write)
- **Discussion Threads**: Comment threads on specific nodes or connections

**Cognitive Rationale**: Explaining to others is one of the most powerful learning strategies (Chi et al., 1994). Social comparison reveals alternative mental models. Collaborative knowledge construction distributes cognitive load and exposes blind spots.

---

## Design Principles (Safeguards Against Learned Helplessness)

1. **User Must Read**: Graph enhances but never replaces reading original text
2. **Generation Before Reception**: Users attempt explanations before seeing AI's
3. **Effort is Required**: No one-click "master this" buttons—understanding requires engagement
4. **Adaptive Scaffolding**: Support fades as competence grows
5. **Transparency**: Always show source text, never black-box AI explanations
6. **Process Over Product**: System rewards engagement and iteration, not just completion