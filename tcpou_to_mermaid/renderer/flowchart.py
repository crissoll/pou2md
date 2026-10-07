from __future__ import annotations
from collections import defaultdict
from ..model.flow_graph import FlowNode, FlowEdge, NetworkDiagram, FlowGraph


class FlowchartRenderer:
    """Renders FlowGraph or NetworkDiagram into Mermaid flowchart LR strings with straight lines & bifurcation."""

    def __init__(self, curve: str | None = "stepAfter", bifurcate: bool = True):
        self.curve = curve
        self.bifurcate = bifurcate

    def render_network(self, network: NetworkDiagram, is_ld: bool = False) -> str:
        """Render a single network into a Mermaid flowchart."""
        lines: list[str] = []
        if self.curve:
            lines.append(f"%%{{ init: {{ 'flowchart': {{ 'curve': '{self.curve}' }} }} }}%%")
        lines.append("flowchart LR")

        subgraph_label = f" Network {network.index} "
        if network.label:
            subgraph_label = f" Network {network.index} — Label: {network.label} "

        indent = "    "
        if is_ld:
            lines.append(f"    subgraph Network_{network.index} [\"{subgraph_label}\"]")
            indent = "        "
            lines.append(f"{indent}direction LR")

        nodes = list(network.nodes)
        edges = list(network.edges)
        has_junction = False

        if self.bifurcate:
            nodes, edges, has_junction = self._apply_bifurcation(nodes, edges)

        # In Ladder Diagram (LD), add Left and Right Power Rails
        rails: list[FlowNode] = []
        if is_ld:
            l_rail_id = f"N{network.index}_L"
            r_rail_id = f"N{network.index}_R"
            l_rail = FlowNode(id=l_rail_id, label="|", node_type="RAIL", shape="rectangle")
            r_rail = FlowNode(id=r_rail_id, label="|", node_type="RAIL", shape="rectangle")
            rails = [l_rail, r_rail]

            incoming = {e.target_id for e in edges}
            root_contacts = [n for n in nodes if n.node_type == "CONTACT" and n.id not in incoming]

            outgoing = {e.source_id for e in edges}
            terminal_coils = [n for n in nodes if n.node_type == "COIL" and n.id not in outgoing]

            rail_edges_left = [
                FlowEdge(source_id=l_rail_id, target_id=rc.id, label=None, style="rail_left")
                for rc in root_contacts
            ]
            rail_edges_right = [
                FlowEdge(source_id=tc.id, target_id=r_rail_id, label=None, style="rail_right")
                for tc in terminal_coils
            ]

            edges = rail_edges_left + edges + rail_edges_right

        # Categorize nodes into rails, inputs/contacts, boxes/operators, junctions, and outputs/coils
        contacts: list[FlowNode] = []
        boxes: list[FlowNode] = []
        coils: list[FlowNode] = []
        junctions: list[FlowNode] = []

        for node in nodes:
            if node.node_type == "JUNCTION":
                junctions.append(node)
            elif node.node_type in ("INPUT", "OPERAND", "CONTACT"):
                contacts.append(node)
            elif node.node_type in ("BOX", "OPERATOR", "PROGRAM"):
                boxes.append(node)
            elif node.node_type in ("OUTPUT", "COIL", "LABEL"):
                coils.append(node)
            elif node.node_type != "RAIL":
                contacts.append(node)

        if rails:
            lines.append(f"{indent}%% --- Power Rails ---")
            for node in rails:
                lines.append(f'{indent}{node.id}["|"]')
            lines.append("")

        if contacts:
            comment = "%% --- Contacts ---" if is_ld else "%% --- Operands / Variables ---"
            lines.append(f"{indent}{comment}")
            for node in contacts:
                lines.append(self._format_node(node, indent))
            lines.append("")

        if boxes:
            comment = "%% --- Function Blocks ---" if is_ld else "%% --- Function Blocks & Operators ---"
            lines.append(f"{indent}{comment}")
            for node in boxes:
                lines.append(self._format_node(node, indent))
            lines.append("")

        if junctions:
            lines.append(f"{indent}%% --- Bifurcation Junctions ---")
            for node in junctions:
                lines.append(self._format_node(node, indent))
            lines.append("")

        if coils:
            comment = "%% --- Coils / Jumps ---" if is_ld else "%% --- Outputs ---"
            lines.append(f"{indent}{comment}")
            for node in coils:
                lines.append(self._format_node(node, indent))
            lines.append("")

        if edges:
            comment = "%% --- Continuity ---" if is_ld else "%% --- Wiring ---"
            lines.append(f"{indent}{comment}")
            for edge in edges:
                lines.append(self._format_edge(edge, indent, is_ld=is_ld))

        if has_junction:
            lines.append("")
            lines.append(f"{indent}classDef junction fill:#333,stroke:#333,width:6px,height:6px")

        # Strip any trailing empty lines inside block
        while lines and lines[-1].strip() == "":
            lines.pop()

        if is_ld:
            lines.append("    end")

        return "\n".join(lines)

    def render_cfc(self, graph: FlowGraph) -> str:
        """Render a CFC flow graph into a Mermaid flowchart."""
        lines: list[str] = []
        if self.curve:
            lines.append(f"%%{{ init: {{ 'flowchart': {{ 'curve': '{self.curve}' }} }} }}%%")
        lines.append("flowchart LR")
        indent = "    "

        nodes = graph.nodes
        edges = graph.edges
        has_junction = False

        if self.bifurcate:
            nodes, edges, has_junction = self._apply_bifurcation(nodes, edges)

        inputs: list[FlowNode] = []
        junctions: list[FlowNode] = []
        operators: list[FlowNode] = []
        fbs: list[FlowNode] = []
        programs: list[FlowNode] = []
        outputs: list[FlowNode] = []

        for node in nodes:
            if node.node_type == "INPUT":
                inputs.append(node)
            elif node.node_type == "JUNCTION":
                junctions.append(node)
            elif node.node_type == "OPERATOR":
                operators.append(node)
            elif node.node_type == "BOX":
                fbs.append(node)
            elif node.node_type == "PROGRAM":
                programs.append(node)
            elif node.node_type == "OUTPUT":
                outputs.append(node)

        if inputs:
            lines.append(f"{indent}%% --- Input Variables ---")
            for n in inputs:
                lines.append(self._format_node(n, indent))
            lines.append("")

        if junctions:
            lines.append(f"{indent}%% --- Bifurcation Junctions ---")
            for n in junctions:
                lines.append(self._format_node(n, indent))
            lines.append("")

        if operators:
            lines.append(f"{indent}%% --- Operators ---")
            for n in operators:
                lines.append(self._format_node(n, indent))
            lines.append("")

        if fbs:
            lines.append(f"{indent}%% --- Function Blocks ---")
            for n in fbs:
                lines.append(self._format_node(n, indent))
            lines.append("")

        if programs:
            lines.append(f"{indent}%% --- Program Calls ---")
            for n in programs:
                lines.append(self._format_node(n, indent))
            lines.append("")

        if outputs:
            lines.append(f"{indent}%% --- Output Variables ---")
            for n in outputs:
                lines.append(self._format_node(n, indent))
            lines.append("")

        if edges:
            lines.append(f"{indent}%% --- Wiring ---")
            for edge in edges:
                lines.append(self._format_edge(edge, indent, is_ld=False))

        if has_junction:
            lines.append("")
            lines.append(f"{indent}classDef junction fill:#333,stroke:#333,width:6px,height:6px")

        while lines and lines[-1].strip() == "":
            lines.pop()

        return "\n".join(lines)

    def _apply_bifurcation(
        self, nodes: list[FlowNode], edges: list[FlowEdge]
    ) -> tuple[list[FlowNode], list[FlowEdge], bool]:
        """
        Group outgoing edges by (source_id, source_pin).
        If an output pin connects to > 1 targets, create a junction node
        and replace the edges with: 1 trunk edge (source -> junction)
        and N branch edges (junction -> target).
        """
        groups: dict[tuple[str, str | None], list[tuple[FlowEdge, str | None, str | None]]] = defaultdict(list)
        for edge in edges:
            lbl = edge.label or ""
            if " → " in lbl:
                src_pin, dst_pin = lbl.split(" → ", 1)
            elif lbl in ("Q", "Q1", "bOut"):
                src_pin, dst_pin = lbl, None
            else:
                src_pin, dst_pin = None, (lbl if lbl else None)
            groups[(edge.source_id, src_pin)].append((edge, src_pin, dst_pin))

        new_nodes = list(nodes)
        new_edges: list[FlowEdge] = []
        has_junction = False

        for (source_id, src_pin), entries in groups.items():
            if len(entries) > 1:
                has_junction = True
                pin_suffix = f"_{src_pin}" if src_pin else ""
                j_id = f"J_{source_id}{pin_suffix}"
                j_node = FlowNode(id=j_id, label="", node_type="JUNCTION", shape="junction")
                new_nodes.append(j_node)

                # Trunk edge
                new_edges.append(
                    FlowEdge(
                        source_id=source_id,
                        target_id=j_id,
                        label=src_pin,
                        style="solid",
                    )
                )

                # Branch edges
                for orig_edge, _, dst_pin in entries:
                    new_edges.append(
                        FlowEdge(
                            source_id=j_id,
                            target_id=orig_edge.target_id,
                            label=dst_pin,
                            style=orig_edge.style,
                        )
                    )
            else:
                for orig_edge, _, _ in entries:
                    new_edges.append(orig_edge)

        return new_nodes, new_edges, has_junction

    def _format_node(self, node: FlowNode, indent: str) -> str:
        """Format a single node definition according to its shape."""
        if node.shape == "junction":
            return f"{indent}{node.id}(( )):::junction"

        label = node.label
        if "\n" in label:
            parts = label.split("\n")
            label_indented = f"\n{indent}".join(parts)
        else:
            label_indented = label

        if node.shape == "stadium":
            return f'{indent}{node.id}(["{label_indented}"])'
        elif node.shape == "hexagon":
            return f'{indent}{node.id}{{{{"{label_indented}"}}}}'
        elif node.shape == "subroutine":
            return f'{indent}{node.id}[["{label_indented}"]]'
        elif node.shape == "rectangle":
            return f'{indent}{node.id}["{label_indented}"]'
        else:
            return f'{indent}{node.id}(["{label_indented}"])'

    def _format_edge(self, edge: FlowEdge, indent: str, is_ld: bool = False) -> str:
        """Format a single directional edge."""
        if is_ld:
            if edge.style == "rail_left":
                return f"{indent}{edge.source_id} --- {edge.target_id}"
            elif edge.label:
                return f'{indent}{edge.source_id} ===|"{edge.label}"| {edge.target_id}'
            else:
                return f"{indent}{edge.source_id} === {edge.target_id}"

        # Standard FBD / CFC edge formatting
        if edge.style == "dotted":
            if edge.label:
                return f'{indent}{edge.source_id} -. "{edge.label}" .-> {edge.target_id}'
            else:
                return f'{indent}{edge.source_id} -.-> {edge.target_id}'
        else:
            if edge.label:
                return f'{indent}{edge.source_id} -- "{edge.label}" --> {edge.target_id}'
            else:
                return f'{indent}{edge.source_id} --> {edge.target_id}'
