from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FlowNode:
    """Represents a node in the signal flow diagram."""
    id: str
    label: str
    node_type: str  # OPERAND, BOX, OPERATOR, PROGRAM, COIL, CONTACT, LABEL
    sub_label: str | None = None
    shape: str = "stadium"  # stadium, subroutine, hexagon, rectangle
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FlowEdge:
    """Represents a directional connection between two nodes."""
    source_id: str
    target_id: str
    label: str | None = None
    style: str = "solid"  # solid, dotted


@dataclass
class NetworkDiagram:
    """Represents a single network (NWL / LD / FBD) within a POU."""
    index: int
    title: str = ""
    label: str = ""
    comment: str = ""
    nodes: list[FlowNode] = field(default_factory=list)
    edges: list[FlowEdge] = field(default_factory=list)


@dataclass
class FlowGraph:
    """Represents the complete implementation logic flow of a POU."""
    language: str  # FBD, CFC, LD, ST
    networks: list[NetworkDiagram] = field(default_factory=list)
    # Direct nodes and edges (used for CFC or single-network representation)
    nodes: list[FlowNode] = field(default_factory=list)
    edges: list[FlowEdge] = field(default_factory=list)
    st_code: str | None = None
