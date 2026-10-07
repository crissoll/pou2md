from __future__ import annotations
from ..model.declaration import PouDeclaration


class ClassDiagramRenderer:
    """Renders a PouDeclaration into a Mermaid classDiagram string."""

    # Visibility prefix mappings for IEC 61131-3 variable groups
    PREFIX_MAP = {
        "VAR_INPUT": "+",
        "VAR_OUTPUT": "-",
        "VAR_IN_OUT": "#",
        "VAR": "",
        "VAR_GLOBAL": "",
        "VAR_STAT": "",
        "VAR_TEMP": "",
    }

    def render(self, decl: PouDeclaration) -> str:
        """Render the class diagram for a POU."""
        lines: list[str] = [
            "classDiagram",
            f"    class {decl.name} {{",
            f"        <<{decl.pou_type}>>",
        ]

        for group in decl.var_groups:
            prefix = self.PREFIX_MAP.get(group.group_type.upper(), "")
            for var in group.variables:
                val_suffix = f" = {var.initial_value}" if var.initial_value is not None else ""
                lines.append(f"        {prefix}{var.data_type} {var.name}{val_suffix}")

        lines.append("    }")
        return "\n".join(lines)
