from __future__ import annotations
import xml.etree.ElementTree as ET
from ..model.flow_graph import FlowNode, FlowEdge, FlowGraph


def _strip_quotes(s: str | None) -> str:
    return s.strip('"') if s else ""


def _clean_id(val: str | None) -> str:
    if not val:
        return ""
    return val.strip('"').rstrip("L")


class CFCParser:
    """Parser for CFC (Continuous Function Chart) implementation format."""

    def parse(self, cfc_elem: ET.Element) -> FlowGraph:
        """Parse a <CFC> element into a FlowGraph."""
        items = cfc_elem.findall(
            './/o[@t="CFCImplementationObject"]/o[@n="Items"]/l2[@n="InnerList"]/o'
        )

        input_elems: list[dict] = []
        output_elems: list[dict] = []
        box_elems: list[dict] = []
        connections: list[dict] = []

        for it in items:
            t = it.attrib.get("t", "")
            if t == "CFCInputElement":
                text = _strip_quotes(it.findtext('./o[@n="Text"]/v[@n="Text"]'))
                pin_id = _clean_id(it.findtext('./o[@n="Output"]/v[@n="Id"]'))
                elem_id = _clean_id(it.findtext('./v[@n="Id"]'))
                input_elems.append({"id": elem_id, "text": text, "pin_id": pin_id})
            elif t == "CFCOutputElement":
                text = _strip_quotes(it.findtext('./o[@n="Text"]/v[@n="Text"]'))
                pin_id = _clean_id(it.findtext('./o[@n="Input"]/v[@n="Id"]'))
                elem_id = _clean_id(it.findtext('./v[@n="Id"]'))
                output_elems.append({"id": elem_id, "text": text, "pin_id": pin_id})
            elif t == "CFCBoxElement":
                kind = _strip_quotes(it.findtext('./v[@n="KindOfCall"]'))
                elem_id = _clean_id(it.findtext('./v[@n="Id"]'))
                in_pins = [
                    _clean_id(p.findtext('./v[@n="Id"]'))
                    for p in it.findall('./o[@n="Inputs"]/l2[@n="InnerList"]/o')
                ]
                out_pins = [
                    _clean_id(p.findtext('./v[@n="Id"]'))
                    for p in it.findall('./o[@n="Outputs"]/l2[@n="InnerList"]/o')
                ]
                texts = [
                    _strip_quotes(t_elem.findtext('./v[@n="Text"]'))
                    for t_elem in it.findall('./o[@n="Texts"]/l2[@n="InnerList"]/o')
                ]
                box_elems.append(
                    {
                        "id": elem_id,
                        "kind": kind,
                        "in_pins": in_pins,
                        "out_pins": out_pins,
                        "texts": texts,
                    }
                )
            elif t == "CFCConnection":
                src = _clean_id(it.findtext('./v[@n="SourcePinId"]'))
                dst = _clean_id(it.findtext('./v[@n="DestPinId"]'))
                conn_id = _clean_id(it.findtext('./v[@n="Id"]'))
                connections.append({"id": conn_id, "src": src, "dst": dst})

        pin_to_node: dict[str, tuple[str, str]] = {}
        nodes: dict[str, FlowNode] = {}

        # 1. Inputs
        for inp in input_elems:
            name = inp["text"]
            short_id = name.split(".")[-1]
            nodes[short_id] = FlowNode(
                id=short_id,
                label=name,
                shape="stadium",
                node_type="INPUT",
            )
            pin_to_node[inp["pin_id"]] = (short_id, "")

        # 2. Outputs
        for out in output_elems:
            name = out["text"]
            short_id = name.split(".")[-1]
            nodes[short_id] = FlowNode(
                id=short_id,
                label=name,
                shape="stadium",
                node_type="OUTPUT",
            )
            pin_to_node[out["pin_id"]] = (short_id, "")

        # 3. Boxes
        box_type_counts: dict[str, int] = {}
        for box in box_elems:
            kind = box["kind"]
            n_in = len(box["in_pins"])
            n_out = len(box["out_pins"])
            box_type = (
                box["texts"][n_in + n_out]
                if len(box["texts"]) > (n_in + n_out)
                else "Box"
            )
            instance = (
                box["texts"][n_in + n_out + 1]
                if len(box["texts"]) > (n_in + n_out + 1)
                else ""
            )

            cnt = box_type_counts.get(box_type, 0) + 1
            box_type_counts[box_type] = cnt

            if kind == "Program":
                node_id = box_type
                shape = "subroutine"
                label = f" {box_type}"
                node_type = "PROGRAM"
            elif kind == "Operator":
                node_id = f"{box_type}{cnt}"
                shape = "hexagon"
                label = box_type
                node_type = "OPERATOR"
            else:  # FunctionBlock
                node_id = f"{box_type}{cnt}"
                shape = "subroutine"
                label = f"{box_type}\n{instance}"
                node_type = "BOX"

            nodes[node_id] = FlowNode(
                id=node_id,
                label=label,
                shape=shape,
                node_type=node_type,
            )

            for idx, p_id in enumerate(box["in_pins"]):
                lbl = box["texts"][idx] if idx < len(box["texts"]) else ""
                pin_to_node[p_id] = (node_id, lbl)

            for idx, p_id in enumerate(box["out_pins"]):
                lbl = (
                    box["texts"][n_in + idx]
                    if (n_in + idx) < len(box["texts"])
                    else ""
                )
                pin_to_node[p_id] = (node_id, lbl)

        # 4. Connections
        edges: list[FlowEdge] = []
        for conn in connections:
            src_info = pin_to_node.get(conn["src"])
            dst_info = pin_to_node.get(conn["dst"])
            if src_info and dst_info:
                src_node, src_lbl = src_info
                dst_node, dst_lbl = dst_info
                if src_lbl and dst_lbl:
                    lbl = f"{src_lbl} → {dst_lbl}"
                elif src_lbl:
                    lbl = src_lbl
                elif dst_lbl:
                    lbl = dst_lbl
                else:
                    lbl = None

                edges.append(
                    FlowEdge(
                        source_id=src_node,
                        target_id=dst_node,
                        label=lbl,
                        style="solid",
                    )
                )

        return FlowGraph(
            language="CFC",
            nodes=list(nodes.values()),
            edges=edges,
        )
