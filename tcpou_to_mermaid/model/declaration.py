from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Variable:
    """Represents a single variable declaration."""
    name: str
    data_type: str
    initial_value: str | None = None
    comment: str | None = None


@dataclass
class VarGroup:
    """Represents a block of variables (e.g. VAR_INPUT, VAR_OUTPUT, VAR)."""
    group_type: str  # VAR_INPUT, VAR_OUTPUT, VAR, VAR_IN_OUT, VAR_GLOBAL, VAR_STAT, etc.
    variables: list[Variable] = field(default_factory=list)


@dataclass
class PouDeclaration:
    """Represents the complete parsed declaration of an IEC 61131-3 POU."""
    name: str
    pou_type: str  # PROGRAM, FUNCTION_BLOCK, FUNCTION
    return_type: str | None = None  # For FUNCTION
    extends: str | None = None
    implements: list[str] = field(default_factory=list)
    var_groups: list[VarGroup] = field(default_factory=list)

    def get_variables_by_group(self, group_type: str) -> list[Variable]:
        """Return all variables belonging to the specified group type."""
        for g in self.var_groups:
            if g.group_type.upper() == group_type.upper():
                return g.variables
        return []
