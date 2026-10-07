from __future__ import annotations
import re
import xml.etree.ElementTree as ET
from ..model.flow_graph import FlowNode, FlowEdge, NetworkDiagram, FlowGraph


def _strip_quotes(s: str | None) -> str:
    return s.strip('"') if s else ""


def _clean_id(val: str | None) -> str:
    if not val:
        return ""
    return val.strip('"').rstrip('L')


class NWLParser:
    """Parser for NWL (Network List) implementation format (FBD and LD)."""

    def parse(self, nwl_elem: ET.Element) -> FlowGraph:
        """Parse an <NWL> element into a FlowGraph."""
        view_mode_elem = nwl_elem.find('.//v[@n="DefaultViewMode"]')
        view_mode = _strip_quotes(view_mode_elem.text if view_mode_elem is not None else "Fbd")
        is_ld = view_mode.lower() == "ld"
        lang = "LD" if is_ld else "FBD"

        network_elements = nwl_elem.findall('.//l2[@n="NetworkList"]/o')
        networks: list[NetworkDiagram] = []

        multi_network = len(network_elements) > 1

        for idx, net_elem in enumerate(network_elements, 1):
            title = _strip_quotes(net_elem.findtext('./v[@n="Title"]'))
            label = _strip_quotes(net_elem.findtext('./v[@n="Label"]'))
            comment = _strip_quotes(net_elem.findtext('./v[@n="Comment"]'))

            prefix = f"N{idx}_" if (multi_network or is_ld) else ""

            parser_net = _NWLNetworkWalker(is_ld=is_ld, prefix=prefix)

            items_container = net_elem.find('./l2[@n="NetworkItems"]')
            if items_container is not None:
                cet = items_container.attrib.get('cet', '')
                items = items_container.findall('./o')
                for it in items:
                    if not it.attrib.get('t'):
                        it.attrib['t'] = cet
                    parser_net.parse_item(it)

            network_diag = NetworkDiagram(
                index=idx,
                title=title,
                label=label,
                comment=comment,
                nodes=list(parser_net.nodes.values()),
                edges=parser_net.edges,
            )
            networks.append(network_diag)

        all_nodes: list[FlowNode] = []
        all_edges: list[FlowEdge] = []
        for n in networks:
            all_nodes.extend(n.nodes)
            all_edges.extend(n.edges)

        return FlowGraph(
            language=lang,
            networks=networks,
            nodes=all_nodes,
            edges=all_edges,
        )


class _NWLNetworkWalker:
    """Helper class to traverse the AST of a single NWL Network."""

    def __init__(self, is_ld: bool, prefix: str):
        self.is_ld = is_ld
        self.prefix = prefix
        self.nodes: dict[str, FlowNode] = {}
        self.edges: list[FlowEdge] = []
        self.id_counts: dict[str, int] = {}

    def get_unique_id(self, base_id: str) -> str:
        if not base_id:
            base_id = "node"
        if base_id not in self.id_counts:
            self.id_counts[base_id] = 1
            return base_id
        else:
            self.id_counts[base_id] += 1
            return f"{base_id}_{self.id_counts[base_id]}"

    def parse_item(
        self,
        item: ET.Element,
        parent_box_id: str | None = None,
        in_param: str = "",
        in_flags: int = 0,
    ) -> tuple[str | None, str]:
        t = item.attrib.get("t", "")

        if t == "BoxTreeAssign" or item.find('./o[@n="RValue"]') is not None:
            rvalue = item.find('./o[@n="RValue"]')
            output_items = item.findall('.//l2[@n="OutputItems"]/o')

            rval_id, rval_out_param = (
                self.parse_item(rvalue) if rvalue is not None else (None, "")
            )

            if rval_id:
                for out_op in output_items:
                    op_name = _strip_quotes(out_op.findtext('./v[@n="Operand"]'))
                    op_type = _strip_quotes(out_op.findtext('./v[@n="Type"]'))
                    flags = int(out_op.findtext('.//v[@n="Flags"]') or "0")
                    is_bool = (out_op.findtext('./v[@n="Boolean"]') or "").lower() == "true"

                    out_id = self.make_operand_node(
                        op_name, op_type, is_bool, is_output=True, flags=flags
                    )
                    edge_label = rval_out_param if rval_out_param else None
                    self.edges.append(
                        FlowEdge(
                            source_id=rval_id,
                            target_id=out_id,
                            label=edge_label,
                            style="solid",
                        )
                    )

            # Pass-through to parent box if nested
            if parent_box_id and rval_id:
                edge_label = ""
                if rval_out_param and in_param:
                    edge_label = f"{rval_out_param} → {in_param}"
                elif rval_out_param:
                    edge_label = rval_out_param
                elif in_param:
                    edge_label = in_param

                style = "dotted" if in_flags == 1 else "solid"
                if in_flags == 1 and not self.is_ld:
                    edge_label = (
                        "○ (negated)" if not edge_label else f"○ {edge_label}"
                    )

                self.edges.append(
                    FlowEdge(
                        source_id=rval_id,
                        target_id=parent_box_id,
                        label=edge_label or None,
                        style=style,
                    )
                )

            return rval_id, rval_out_param

        elif t == "BoxTreeBox" or item.find('./v[@n="BoxType"]') is not None:
            box_type = _strip_quotes(item.findtext('./v[@n="BoxType"]'))
            instance = _strip_quotes(
                item.findtext('./o[@n="Instance"]/v[@n="Operand"]')
            )
            call_type = _strip_quotes(item.findtext('./v[@n="CallType"]'))

            in_params = [
                _strip_quotes(v.text)
                for v in item.findall('./o[@n="InputParam"]/l2[@n="Names"]/v')
            ]
            out_params = [
                _strip_quotes(v.text)
                for v in item.findall('./o[@n="OutputParam"]/l2[@n="Names"]/v')
            ]
            input_flags = [
                int(v.text or "0")
                for v in item.findall('./l2[@n="InputFlags"]/o/v[@n="Flags"]')
            ]

            # In Ladder Diagram (LD), an AND operator is represented by series connections
            if self.is_ld and box_type == "AND":
                input_items = item.findall('./l2[@n="InputItems"]/o')
                if len(input_items) >= 2:
                    in0_id, in0_out = self.parse_item(input_items[0])
                    in1_id, in1_out = self.parse_item(input_items[1])
                    if in0_id and in1_id:
                        self.edges.append(
                            FlowEdge(
                                source_id=in0_id,
                                target_id=in1_id,
                                label=in0_out or None,
                                style="solid",
                            )
                        )
                    if parent_box_id:
                        self.edges.append(
                            FlowEdge(
                                source_id=in1_id,
                                target_id=parent_box_id,
                                label=in_param or None,
                                style="solid",
                            )
                        )
                    return in1_id, in1_out

            box_id = self.make_box_node(box_type, instance, call_type)

            if parent_box_id:
                edge_label = ""
                out_param_name = out_params[0] if out_params else ""
                if out_param_name and in_param:
                    edge_label = f"{out_param_name} → {in_param}"
                elif out_param_name:
                    edge_label = out_param_name
                elif in_param:
                    edge_label = in_param

                style = "dotted" if in_flags == 1 else "solid"
                if in_flags == 1 and not self.is_ld:
                    edge_label = (
                        "○ (negated)" if not edge_label else f"○ {edge_label}"
                    )

                self.edges.append(
                    FlowEdge(
                        source_id=box_id,
                        target_id=parent_box_id,
                        label=edge_label or None,
                        style=style,
                    )
                )

            input_items = item.findall('./l2[@n="InputItems"]/o')
            for idx, inp in enumerate(input_items):
                p_name = in_params[idx] if idx < len(in_params) else ""
                p_flag = input_flags[idx] if idx < len(input_flags) else 0
                self.parse_item(
                    inp, parent_box_id=box_id, in_param=p_name, in_flags=p_flag
                )

            primary_out = out_params[0] if out_params else ""
            return box_id, primary_out

        elif t == "BoxTreeOperand" or item.find('./o[@n="Operand"]') is not None:
            op_elem = item.find('./o[@n="Operand"]')
            if op_elem is None:
                return None, ""
            op_name = _strip_quotes(op_elem.findtext('./v[@n="Operand"]'))
            op_type = _strip_quotes(op_elem.findtext('./v[@n="Type"]'))
            flags = int(op_elem.findtext('.//v[@n="Flags"]') or "0")
            is_bool = (op_elem.findtext('./v[@n="Boolean"]') or "").lower() == "true"

            op_id = self.make_operand_node(
                op_name,
                op_type,
                is_bool,
                is_output=False,
                flags=flags,
                in_param=in_param,
                in_flags=in_flags,
            )

            if parent_box_id:
                style = "dotted" if in_flags == 1 else "solid"
                edge_label = in_param
                if in_flags == 1 and not self.is_ld:
                    edge_label = (
                        "○ (negated)" if not edge_label else f"○ {edge_label}"
                    )

                self.edges.append(
                    FlowEdge(
                        source_id=op_id,
                        target_id=parent_box_id,
                        label=edge_label or None,
                        style=style,
                    )
                )

            return op_id, ""

        return None, ""

    def make_operand_node(
        self,
        name: str,
        op_type: str,
        is_bool: bool,
        is_output: bool = False,
        flags: int = 0,
        in_param: str = "",
        in_flags: int = 0,
    ) -> str:
        clean = name.split(".")[-1]
        clean = clean.replace("#", "").replace(" ", "_")
        clean = re.sub(r"[^A-Za-z0-9_]", "", clean)

        if self.prefix:
            if clean == "T1s":
                if "On" in in_param:
                    base = f"{self.prefix}T1s_On"
                elif "Off" in in_param:
                    base = f"{self.prefix}T1s_Off"
                else:
                    base = f"{self.prefix}{clean}"
            elif name.startswith("fbTimer") and "." in name:
                base = f"{self.prefix}{name.replace('.', '')}"
            else:
                base = f"{self.prefix}{clean}"
        else:
            if "." in name:
                base = name.replace(".", "")
            else:
                base = clean

        node_id = self.get_unique_id(base)

        if self.is_ld:
            if flags == 4:
                node_type = "LABEL"
                label = f"▶ {name}"
                shape = "rectangle"
            elif is_output:
                node_type = "COIL"
                label = f"—( )—<br/>{name}"
                shape = "rectangle"
            elif is_bool:
                node_type = "CONTACT"
                label = f"—┤/├—<br/>{name}" if in_flags == 1 else f"—┤ ├—<br/>{name}"
                shape = "rectangle"
            else:
                node_type = "OPERAND"
                label = name
                shape = "rectangle"
        else:
            if flags == 4:
                node_type = "LABEL"
                label = f"▶ {name}\n(jump label)"
            elif is_output:
                node_type = "OUTPUT"
                label = name
            else:
                node_type = "OPERAND"
                label = name
            shape = "stadium"

        self.nodes[node_id] = FlowNode(
            id=node_id,
            label=label,
            node_type=node_type,
            shape=shape,
        )
        return node_id

    def make_box_node(self, box_type: str, instance: str, call_type: str) -> str:
        if self.prefix:
            if instance:
                if box_type == "FB_Blinker":
                    base = f"{self.prefix}Blinker"
                else:
                    base = f"{self.prefix}{box_type}"
            else:
                base = f"{self.prefix}{box_type}"
        else:
            if instance:
                inst_suffix = instance.replace("fbTimer", "_").replace("fb", "")
                base = f"{box_type}{inst_suffix}"
            else:
                base = f"{box_type}1"

        box_id = self.get_unique_id(base)

        if not instance or call_type == "Operator" or box_type == "AND":
            label = (
                f"{box_type} (&)"
                if (box_type == "AND" and not self.is_ld)
                else box_type
            )
            shape = "hexagon"
            node_type = "OPERATOR"
        else:
            label = f"{box_type}<br/>{instance}" if self.is_ld else f"{box_type}\n{instance}"
            shape = "subroutine"
            node_type = "BOX"

        self.nodes[box_id] = FlowNode(
            id=box_id,
            label=label,
            node_type=node_type,
            shape=shape,
        )
        return box_id

