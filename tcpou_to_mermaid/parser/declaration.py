from __future__ import annotations
import re
from ..model.declaration import Variable, VarGroup, PouDeclaration


class DeclarationParser:
    """Parser for IEC 61131-3 POU declaration text blocks."""

    # Matches header: PROGRAM Name, FUNCTION_BLOCK Name, FUNCTION Name : ReturnType
    HEADER_PATTERN = re.compile(
        r"^\s*(PROGRAM|FUNCTION_BLOCK|FUNCTION)\s+([A-Za-z0-9_]+)"
        r"(?:\s*:\s*([A-Za-z0-9_]+))?"
        r"(?:\s+EXTENDS\s+([A-Za-z0-9_]+))?"
        r"(?:\s+IMPLEMENTS\s+([A-Za-z0-9_,\s]+))?",
        re.MULTILINE | re.IGNORECASE,
    )

    # Matches VAR blocks: VAR_INPUT, VAR_OUTPUT, VAR_IN_OUT, VAR_GLOBAL, VAR_STAT, VAR_TEMP, VAR
    VAR_BLOCK_PATTERN = re.compile(
        r"(VAR_INPUT|VAR_OUTPUT|VAR_IN_OUT|VAR_GLOBAL|VAR_STAT|VAR_TEMP|VAR_EXTERNAL|VAR_CONFIG|VAR)"
        r"(?:\s+(?:RETAIN|PERSISTENT|CONSTANT|NON_RETAIN))*[\r\n]+"
        r"(.*?)"
        r"END_VAR",
        re.DOTALL | re.IGNORECASE,
    )

    def parse(self, text: str) -> PouDeclaration:
        """Parse IEC 61131-3 declaration text into a PouDeclaration object."""
        clean_text = text.strip()
        header_match = self.HEADER_PATTERN.search(clean_text)

        if not header_match:
            # Fallback if no explicit header found
            pou_type = "PROGRAM"
            name = "Unknown"
            return_type = None
            extends = None
            implements = []
        else:
            pou_type = header_match.group(1).upper()
            name = header_match.group(2)
            return_type = header_match.group(3)
            extends = header_match.group(4)
            raw_implements = header_match.group(5)
            implements = (
                [i.strip() for i in raw_implements.split(",") if i.strip()]
                if raw_implements
                else []
            )

        var_groups: list[VarGroup] = []

        # Find all VAR blocks
        for block_match in self.VAR_BLOCK_PATTERN.finditer(clean_text):
            group_type = block_match.group(1).upper()
            body = block_match.group(2)
            variables = self._parse_variables(body)
            var_groups.append(VarGroup(group_type=group_type, variables=variables))

        return PouDeclaration(
            name=name,
            pou_type=pou_type,
            return_type=return_type,
            extends=extends,
            implements=implements,
            var_groups=var_groups,
        )

    def _parse_variables(self, block_body: str) -> list[Variable]:
        """Extract variable declarations from a VAR block body."""
        variables: list[Variable] = []

        # Strip block comments (* ... *)
        cleaned = re.sub(r"\(\*.*?\*\)", "", block_body, flags=re.DOTALL)

        lines = cleaned.splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Extract inline comment //
            comment = None
            if "//" in line:
                line_part, comment_part = line.split("//", 1)
                line = line_part.strip()
                comment = comment_part.strip()

            if not line or not line.endswith(";"):
                continue

            line_without_semi = line[:-1].strip()
            if ":" not in line_without_semi:
                continue

            raw_names, rest = line_without_semi.split(":", 1)
            raw_names = raw_names.strip()
            rest = rest.strip()

            # Check for initial value :=
            init_val = None
            if ":=" in rest:
                raw_type, raw_init = rest.split(":=", 1)
                data_type = raw_type.strip()
                init_val = raw_init.strip()
            else:
                data_type = rest.strip()

            # In case multiple variable names are declared on the same line: a, b : INT;
            for single_name in raw_names.split(","):
                single_name = single_name.strip()
                if single_name:
                    variables.append(
                        Variable(
                            name=single_name,
                            data_type=data_type,
                            initial_value=init_val,
                            comment=comment,
                        )
                    )

        return variables
