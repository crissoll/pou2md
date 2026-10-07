from __future__ import annotations
from pathlib import Path
from ..model.declaration import PouDeclaration
from ..model.flow_graph import FlowGraph
from ..renderer.class_diagram import ClassDiagramRenderer
from ..renderer.flowchart import FlowchartRenderer


class MarkdownWriter:
    """Combines declarations, flowcharts, and ST source into comprehensive Markdown files."""

    LANG_DISPLAY = {
        "FBD": "FBD (Function Block Diagram)",
        "LD": "LD (Ladder Diagram) via NWL",
        "CFC": "CFC (Continuous Function Chart)",
        "ST": "ST (Structured Text) — *flowchart not generated*",
    }

    def __init__(self, curve: str | None = "step", bifurcate: bool = True):
        self.class_renderer = ClassDiagramRenderer()
        self.flow_renderer = FlowchartRenderer(curve=curve, bifurcate=bifurcate)

    def generate(
        self,
        decl: PouDeclaration,
        graph: FlowGraph,
        source_filename: str,
    ) -> str:
        """Generate complete Markdown text with embedded Mermaid diagrams."""
        lang_str = self.LANG_DISPLAY.get(graph.language, graph.language)

        lines: list[str] = [
            f"# {decl.name}",
            "",
            f"> **POU Type:** {decl.pou_type}  ",
            f"> **Source:** `{source_filename}`  ",
            f"> **Implementation Language:** {lang_str}",
            "",
            "## Declaration",
            "",
            "```mermaid",
            self.class_renderer.render(decl),
            "```",
            "",
        ]

        if graph.language == "ST":
            lines.extend(
                [
                    "## Implementation (ST)",
                    "",
                    "> [!NOTE]",
                    "> This POU uses Structured Text. No flowchart diagram is generated — the source code is shown below.",
                    "",
                    "```iecst",
                    graph.st_code or "",
                    "```",
                ]
            )
        elif graph.language == "CFC":
            lines.extend(
                [
                    "## Implementation (CFC)",
                    "",
                    "```mermaid",
                    self.flow_renderer.render_cfc(graph),
                    "```",
                ]
            )
        elif graph.language in ("FBD", "LD"):
            is_ld = graph.language == "LD"
            for net in graph.networks:
                net_header = f"## Implementation ({graph.language}) — Network {net.index}"
                if net.label:
                    net_header += f" (Label: {net.label})"

                lines.append(net_header)
                lines.append("")

                if net.comment:
                    lines.append(net.comment)
                    lines.append("")

                lines.append("```mermaid")
                lines.append(self.flow_renderer.render_network(net, is_ld=is_ld))
                lines.append("```")
                lines.append("")

        return "\n".join(lines).rstrip() + "\n"
