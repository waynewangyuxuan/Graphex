"""
Knowledge graph container and operations.
"""

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from .nodes import Node
from .edges import Edge


class GraphMetadata(BaseModel):
    """Metadata for the knowledge graph."""

    document_ids: list[str] = Field(default_factory=list)
    created_at: Optional[str] = None
    version: str = "0.1.0"


class KnowledgeGraph(BaseModel):
    """
    Container for extracted knowledge graph.

    Stores nodes and edges with source tracking.
    """

    nodes: dict[str, Node] = Field(default_factory=dict)
    edges: dict[str, Edge] = Field(default_factory=dict)
    metadata: GraphMetadata = Field(default_factory=GraphMetadata)

    def add_node(self, node: Node) -> None:
        """Add a node to the graph."""
        self.nodes[node.id] = node

    def add_edge(self, edge: Edge) -> None:
        """Add an edge to the graph."""
        if edge.source_id not in self.nodes:
            raise ValueError(f"Source node {edge.source_id} not found")
        if edge.target_id not in self.nodes:
            raise ValueError(f"Target node {edge.target_id} not found")
        self.edges[edge.id] = edge

    def get_node(self, node_id: str) -> Optional[Node]:
        """Get a node by ID."""
        return self.nodes.get(node_id)

    def get_edge(self, edge_id: str) -> Optional[Edge]:
        """Get an edge by ID."""
        return self.edges.get(edge_id)

    def get_node_edges(self, node_id: str) -> list[Edge]:
        """Get all edges connected to a node."""
        return [
            edge
            for edge in self.edges.values()
            if edge.source_id == node_id or edge.target_id == node_id
        ]

    def get_outgoing_edges(self, node_id: str) -> list[Edge]:
        """Get edges where node is the source."""
        return [edge for edge in self.edges.values() if edge.source_id == node_id]

    def get_incoming_edges(self, node_id: str) -> list[Edge]:
        """Get edges where node is the target."""
        return [edge for edge in self.edges.values() if edge.target_id == node_id]

    def to_json(self, path: Path) -> None:
        """Save graph to JSON file."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, path: Path) -> "KnowledgeGraph":
        """Load graph from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.model_validate(data)

    def __len__(self) -> int:
        return len(self.nodes)

    def summary(self) -> str:
        """Return a summary of the graph."""
        return f"KnowledgeGraph(nodes={len(self.nodes)}, edges={len(self.edges)})"
