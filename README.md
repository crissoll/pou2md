# TcPOU to Mermaid Converter

[![Python Versions](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A modular Python tool that converts Beckhoff TwinCAT 3 `.TcPOU` files into Mermaid diagrams embedded in Markdown (`.md`) documents.

## Features

- **Class Diagrams (`classDiagram`)**: Automatically extracts IEC 61131-3 declarations (`PROGRAM`, `FUNCTION_BLOCK`, `FUNCTION`) with variable sections (`VAR_INPUT`, `VAR_OUTPUT`, `VAR_IN_OUT`, `VAR`), types, and initial values.
- **Continuous Function Chart (CFC)**: Reconstructs the signal flow graph (`flowchart LR`) from `<CFC>` XML structures, resolving pins, operators, function blocks, program calls, and wiring.
- **Function Block Diagram (FBD)**: Recursively parses `<NWL>` trees, resolving nested calls, pass-through assignments, and negated inputs.
- **Ladder Diagram (LD)**: Automatically detects LD view mode, formatting contacts (`┤├`), coils (`( )`), and jump labels (`▶ Label`).
- **Structured Text (ST)**: Embeds the original IEC 61131-3 source code in an `iecst` code block alongside the declaration class diagram.
- **Zero External Dependencies**: Pure Python standard library implementation (`xml.etree.ElementTree`, `re`, `argparse`, `dataclasses`, `pathlib`).

## Architecture

```
tcpou_to_mermaid/
├── __init__.py
├── __main__.py          # CLI entry point
├── converter.py         # Main conversion orchestrator
├── model/
│   ├── declaration.py   # PouDeclaration, VarGroup, Variable dataclasses
│   └── flow_graph.py    # FlowNode, FlowEdge, NetworkDiagram, FlowGraph dataclasses
├── parser/
│   ├── declaration.py   # IEC 61131-3 CDATA declaration parser
│   ├── nwl_parser.py    # Network List parser (FBD & LD)
│   ├── cfc_parser.py    # Continuous Function Chart parser
│   └── st_parser.py     # Structured Text parser
├── renderer/
│   ├── class_diagram.py # Mermaid classDiagram generator
│   └── flowchart.py     # Mermaid flowchart LR generator
└── writer/
    └── markdown.py      # Markdown document generator
```

## Installation & Global Usage

To call the converter from **any folder or terminal**, install it in editable mode:
```bash
pip install -e .
```

Once installed, `tcpou-to-mermaid`, `tcpou_to_mermaid`, and the short alias `pou2md` are all available system-wide:

```bash
# Call from anywhere using the short alias:
pou2md path/to/my_pou.TcPOU -o output/
pou2md path/to/project/ -r -o output/
pou2md path/to/project/ -r -u -o complete_doc.md
```

You can also still use the standard `python -m` syntax:
```bash
python -m tcpou_to_mermaid <args>
```

### Print to stdout
```bash
python -m tcpou_to_mermaid POUs/POUs/FB_Blinker.TcPOU --stdout
```

### Batch Convert a Directory
```bash
python -m tcpou_to_mermaid POUs/POUs/ -o output/
```

### Recursive Directory Conversion (`-r`)
Recursively searches folder trees for `.TcPOU` files and flattens their relative directory paths into filenames (`foldera--folderb--file.md`):
```bash
python -m tcpou_to_mermaid Project/ -r -o output/
```

### Unified Single File (`-u`)
Combines all converted POUs into a single Markdown document:
```bash
# Save to unified file in directory (default: unified.md)
python -m tcpou_to_mermaid POUs/POUs/ -u -o output/

# Save to a specific file
python -m tcpou_to_mermaid POUs/ -r -u -o full_system.md

# Print unified Markdown directly to stdout
python -m tcpou_to_mermaid POUs/ -r -u --stdout
```

### Visual Styling: Straight Lines & Wire Routing
By default, the converter produces diagrams matching TwinCAT graphical schematics:
- **Straight Orthogonal Lines**: Uses `step` midpoint curve interpolation for clean right-angle wires where arrows enter flush into the node face (`>`).
- **Bifurcation Junctions**: Block outputs with multiple destinations split at a single bifurcation junction dot (`(( ))`) instead of duplicating pin labels.
- **Rank Alignment**: CFC nodes are automatically column-aligned using topological depth and XML visual bounds, preventing wires from cutting through intermediate blocks.

You can customize this behavior via CLI flags:
```bash
# Use smooth curves instead of orthogonal lines:
pou2md path/to/POU.TcPOU --curve basis

# Use direct point-to-point lines:
pou2md path/to/POU.TcPOU --curve linear

# Disable bifurcation (draw separate wires per connection):
pou2md path/to/POU.TcPOU --no-bifurcate

# Repeat input variable blocks per connection in CFC (avoids cross-diagram wires):
pou2md path/to/POU.TcPOU --repeat-inputs
```

## Running Tests

Run the test suite using Python's standard `unittest` module:
```bash
python -m unittest tests/test_converter.py -v
```

## License

This project is licensed under the [MIT License](LICENSE).
