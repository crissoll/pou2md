from __future__ import annotations
import xml.etree.ElementTree as ET
from ..model.flow_graph import FlowGraph


class STParser:
    """Parser for Structured Text (ST) implementations."""

    def parse(self, st_elem: ET.Element) -> FlowGraph:
        """Extract Structured Text source code."""
        st_code = (st_elem.text or "").strip("\r\n")
        return FlowGraph(language="ST", st_code=st_code)
