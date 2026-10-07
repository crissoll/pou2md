# TcPOU to Mermaid Converter

[![CI](https://github.com/your-username/tcpou-to-mermaid/actions/workflows/ci.yml/badge.svg)](https://github.com/your-username/tcpou-to-mermaid/actions/workflows/ci.yml)
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

## Installation & CLI Setup

Install the package using `pip` (editable mode is recommended during development):

```bash
# Editable install (recommended)
pip install -e .

# Or standard install
pip install .
```

Once installed, the CLI tool can be executed from any terminal or directory using `pou2md` (or via Python's `-m` switch):

```bash
# Global CLI command
pou2md [input] [options]

# Standard Python module syntax
python -m tcpou_to_mermaid [input] [options]
```

---

## CLI Reference

### Command Syntax

```bash
pou2md [input] [-o OUTPUT] [-r] [-u] [--single-folder] [--copy-folder-structure] [--exclude PATTERN] [--dry-run] [--clean] [--stdout] [-w] [--curve {step,stepAfter,linear,basis,none}] [--no-bifurcate] [--repeat-inputs]
```

### Options & Arguments

| Argument / Flag | Value Type / Choices | Default | Description |
| :--- | :--- | :--- | :--- |
| `input` *(positional)* | `Path` (file or folder) | `.` *(Current dir)* | Path to a single `.TcPOU` file or a directory containing `.TcPOU` files. |
| `-o`, `--output` | `Path` (folder or `.md` file) | `None` | Destination directory (e.g. `docs/`) or specific file path (e.g. `docs/system.md`). Required for directory input unless `--stdout` is set. |
| `-r`, `--recursive` | `Flag` | `False` | Recursively scan subdirectories for `.TcPOU` files. |
| `-u`, `--unified` | `Flag` | `False` | Merges all converted POUs into a single Markdown document separated by horizontal dividers (`---`). |
| `--single-folder` | `Flag` | Automatic | Also generate individual Markdown files. This is enabled by default unless `--unified` is used alone. |
| `--copy-folder-structure` | `Flag` | `False` | Generate individual Markdown files under matching source subdirectories instead of flattened names. Also enables individual output. |
| `--exclude PATTERN` | `Pattern` | None | Exclude matching filenames or relative paths; repeat the option for multiple patterns. |
| `--stdout` | `Flag` | `False` | Prints generated Markdown directly to `stdout` instead of writing to disk. |
| `--curve` | `step` \| `stepAfter` \| `linear` \| `basis` \| `none` | `step` | Mermaid flowchart wire routing style. `step` generates orthogonal right-angle wires entering blocks horizontally (`>`). |
| `--no-bifurcate` | `Flag` | *(Bifurcation enabled)* | Disables bifurcation junction nodes (`(( ))`), drawing independent wires from the source pin to each destination pin. |
| `--repeat-inputs` | `Flag` | `False` | In CFC diagrams, duplicates input variable blocks next to each connected pin to eliminate long cross-sheet wires. |
| `-w`, `--watch` | `Flag` | `False` | Continuously watches the input file or directory and regenerates Markdown after changes. Press `Ctrl+C` to stop. |
| `--poll-interval` | Seconds | `1.0` | Watcher polling interval. |
| `--debounce-delay` | Seconds | `0.25` | Delay after a detected change before conversion. |
| `--retry-count` | Integer | `3` | Conversion attempts for transient save or network errors. |
| `--retry-delay` | Seconds | `0.5` | Delay between conversion attempts. |
| `-v`, `--verbose` | `Flag` | `False` | Enable diagnostic logging. |
| `--quiet` | `Flag` | `False` | Suppress normal status messages while preserving errors. |
| `--log-format` | `text` \| `json` | `text` | Select human-readable or machine-readable logs. |
| `--dry-run` | `Flag` | `False` | Show planned outputs without writing Markdown or a manifest. |
| `--clean` | `Flag` | `False` | Remove stale outputs previously recorded in the output manifest. Requires `-o`. |
| `-h`, `--help` | `Flag` | - | Display CLI help message and exit. |

---

## Output Resolution Rules

The destination path depends on the input type and flags provided:

| Input Type | Flags | Destination Behavior |
| :--- | :--- | :--- |
| **Single `.TcPOU` file** | *No `-o` or `--stdout`* | Prints generated Markdown directly to `stdout`. |
| **Single `.TcPOU` file** | `-o path/to/dir/` | Creates `path/to/dir/<POU_NAME>.md`. |
| **Single `.TcPOU` file** | `-o path/to/custom.md` | Writes directly to `path/to/custom.md`. |
| **Directory** | `-o path/to/dir/` | Generates individual `<POU_NAME>.md` files inside `path/to/dir/`. |
| **Directory** | `-r -o path/to/dir/` | Recursively scans subfolders; outputs flattened names: `parent--subfolder--<POU_NAME>.md`. |
| **Directory** | `-u -o path/to/dir/` | Combines all POUs into `path/to/dir/unified.md`. |
| **Directory** | `-u -o path/to/custom.md`| Combines all POUs into the exact specified file `path/to/custom.md`. |
| **Directory** | `-u --single-folder -o path/to/dir/` | Writes both individual files and `unified.md`. |
| **Directory** | `-r --copy-folder-structure -o path/to/dir/` | Writes individual files under matching subdirectories. |
| **Directory** | `-u --copy-folder-structure -o path/to/dir/` | Writes both nested individual files and `unified.md`. |
| **Any Input** | `--stdout` | Emits Markdown to terminal `stdout` without creating any files on disk. |

When both individual and unified output are requested with `-o path/to/file.md`,
the unified document uses that exact path and individual files are written to
its parent directory.

## Continuous Watching (`-w`)

Use `-w` to perform an initial conversion and then keep the process running while
watching for added, modified, or removed `.TcPOU` files. The watcher polls the
input path, debounces editor save operations, and releases its lock file when
stopped with `Ctrl+C`.

```bash
# Watch a directory and update individual generated files
pou2md MyPlcProject/ -r -w -o docs/generated/

# Watch a directory and rebuild one unified document
pou2md MyPlcProject/ -r -u -w -o docs/complete_system_manual.md

# Watch one file and print each generated document to stdout
pou2md POUs/FB_Motor.TcPOU -w
```

For directory input, specify `-o/--output` or `--stdout`, just as with a
one-time conversion. When a source file is removed, its generated individual
Markdown file is removed as well; unified output files are rebuilt instead.

Output mode combinations are:

| Flags | Output |
| :--- | :--- |
| *(none)* | Individual files in one output folder |
| `--unified` | Unified file only |
| `--single-folder` | Individual files in one output folder |
| `--unified --single-folder` | Both individual files and unified file |
| `--copy-folder-structure` | Individual files in matching subfolders |
| `--unified --copy-folder-structure` | Both nested individual files and unified file |

The default polling interval is one second, followed by a 250 ms save debounce.
This is normally suitable for mapped drives and SMB shares, but network latency
can make detection slower and a temporarily unavailable share is skipped until
the next poll. The watcher uses an atomic lock-file claim, so two processes
started for the same target cannot both watch it; the second process exits with
an error. Different output targets intentionally use separate locks.

Parsing errors are reported to `stderr` and do not terminate the watcher. This
allows editors to save an incomplete XML document temporarily: the watcher
waits and retries that file after the next change. The same behavior applies to
an incomplete file present when the watcher starts.

Generated Markdown is written through a temporary sibling file and atomically
replaced into place, preventing readers from seeing partially written output.
Use `--exclude` to ignore backup or generated sources, for example:

```bash
pou2md MyPlcProject/ -r -w -o docs/ --exclude "Backup/*" --exclude "*_old.TcPOU"
```

Use `--verbose` for diagnostic status logging or `--quiet` to suppress normal
status messages while retaining errors. Watcher timing can be tuned with
`--poll-interval`, `--debounce-delay`, `--retry-count`, and `--retry-delay`.

## Dry runs, cleanup, and manifests

Use `--dry-run` to inspect the output plan without creating files:

```bash
pou2md MyPlcProject/ -r --copy-folder-structure --dry-run -o docs/
```

When writing to an output directory, the converter maintains
`.pou2md-manifest.json` containing the generated Markdown paths. `--clean`
removes only stale paths recorded in that manifest; it never scans for or
deletes untracked files:

```bash
pou2md MyPlcProject/ -r --clean -o docs/
```

Use JSON logs for automation:

```bash
pou2md MyPlcProject/ -r -w -o docs/ --log-format json
```

---

## Practical CLI Recipes

### 1. Quick Inspection & Terminal Piping
Inspect generated Markdown or pipe directly into tools like `bat`, `glow`, or clipboard utilities:

```bash
# Print POU markdown directly to stdout
pou2md POUs/FB_Motor.TcPOU --stdout

# Pipe output to a markdown viewer (bat, glow, etc.)
pou2md POUs/FB_Motor.TcPOU --stdout | bat -l md

# Copy markdown directly to clipboard (Windows PowerShell)
pou2md POUs/FB_Motor.TcPOU --stdout | Set-Clipboard
```

### 2. Single File Conversion
Convert an individual POU into a specific output directory or custom filename:

```bash
# Save to an output directory (produces output/FB_Motor.md)
pou2md POUs/FB_Motor.TcPOU -o output/

# Save to a specific custom filename
pou2md POUs/FB_Motor.TcPOU -o docs/motor_controller.md
```

### 3. Batch Directory Conversion
Convert all `.TcPOU` files located directly inside a folder:

```bash
pou2md POUs/ -o docs/pous/
```

### 4. Recursive Project Conversion (`-r`)
Recursively scan complete TwinCAT PLC project structures. The converter flattens nested folder hierarchies into distinct, clash-free filenames:

```bash
pou2md MyPlcProject/ -r -o docs/generated/
```

*Example name mapping:*
- `MyPlcProject/Motion/Axes/FB_Axis.TcPOU` &rarr; `docs/generated/Motion--Axes--FB_Axis.md`
- `MyPlcProject/Diagnostics/FB_Logger.TcPOU` &rarr; `docs/generated/Diagnostics--FB_Logger.md`

### 5. Unified Single-Document Generation (`-u`)
Merge your entire PLC library or project into a single Markdown document. Perfect for single-page project wikis, Obsidian vaults, or MkDocs:

```bash
# Save as default unified.md in target directory
pou2md MyPlcProject/ -r -u -o docs/

# Save with a custom documentation filename
pou2md MyPlcProject/ -r -u -o docs/complete_system_manual.md

# Stream the entire unified manual to stdout for downstream processing
pou2md MyPlcProject/ -r -u --stdout > complete_system_manual.md
```

---

## Diagram Layout & Styling Customization

`tcpou-to-mermaid` provides dedicated flags to fine-tune the look and layout of Mermaid flowcharts to match industrial PLC schematics:

### Wire Routing (`--curve`)
Select how signal connection lines are interpolated:

```bash
# Default: Orthogonal right angles entering nodes horizontally (industrial CAD style)
pou2md POUs/FB_Controller.TcPOU -o docs/ --curve step

# Smooth cubic splines (fluid curves)
pou2md POUs/FB_Controller.TcPOU -o docs/ --curve basis

# Direct point-to-point straight lines
pou2md POUs/FB_Controller.TcPOU -o docs/ --curve linear

# Standard Mermaid default curve interpolation
pou2md POUs/FB_Controller.TcPOU -o docs/ --curve none
```

### Output Bifurcation Junctions (`--no-bifurcate`)
When an output pin connects to multiple downstream blocks:
- **Default (Bifurcation enabled)**: Splits wires using a clean junction dot (`(( ))`), preventing duplicate pin labels and visual clutter.
- **`--no-bifurcate`**: Draws separate, independent wires directly from the output pin to every target node.

```bash
# Disable bifurcation junctions
pou2md POUs/FB_Controller.TcPOU -o docs/ --no-bifurcate
```

### CFC Input Variable Duplication (`--repeat-inputs`)
In large Continuous Function Charts (CFC), multiple blocks often share common inputs (e.g. `bEnable` or `stConfig`):
- **Default (`False`)**: Creates a single node for each input variable and connects it across the diagram.
- **`--repeat-inputs`**: Creates an input variable block next to each block pin it feeds, eliminating long feedback loops and wires crossing through the middle of the sheet.

```bash
pou2md POUs/CFC_PlantControl.TcPOU -o docs/ --repeat-inputs
```

---

## CI / CD & Automation Integration

### GitHub Actions Workflow Example
Automatically generate up-to-date Markdown diagrams whenever PLC files are pushed:

```yaml
name: Generate PLC Documentation
on: [push, pull_request]

jobs:
  docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install converter
        run: pip install .
      - name: Build documentation
        run: pou2md src/ -r -u -o docs/plc_architecture.md
      - name: Upload documentation artifact
        uses: actions/upload-artifact@v4
        with:
          name: plc-docs
          path: docs/plc_architecture.md
```

### Shell Automation Scripts

**PowerShell (Windows):**
```powershell
# Convert all POU subdirectories into separate documentation folders
Get-ChildItem -Directory "src/PLC/*" | ForEach-Object {
    pou2md $_.FullName -r -o "docs/$($_.Name)"
}
```

**Bash (Linux / macOS):**
```bash
# Compile documentation for each PLC subsystem
for dir in src/PLC/*/; do
  name=$(basename "$dir")
  pou2md "$dir" -r -u -o "docs/${name}.md"
done
```

---

## Exit Codes

For CI/CD scripts and automated tools, the CLI returns standard status codes:
- `0`: Execution completed successfully.
- `1`: Error encountered (e.g. input path does not exist, or directory input without `-o` / `--stdout`).

## Running Tests

Run the test suite using Python's standard `unittest` module:
```bash
python -m unittest tests/test_converter.py -v
```

## Disclaimer & AI Disclosure

> [!WARNING]
> **Industrial Automation & Safety Notice**
> 
> This tool was developed with the assistance of Artificial Intelligence (AI). 
> 
> * **Visualization Only**: Generated diagrams and Markdown files are intended for documentation and visualization purposes. Never rely solely on this tool for safety audits, formal verification, or machine commissioning.
> * **No Warranty / As-Is**: This software is provided "as is", without warranty of any kind, express or implied.
> * **Limitation of Liability**: The author assumes no responsibility or liability for any errors, omissions, machine downtime, equipment damage, or personal injury resulting from the use of this tool. Use entirely at your own risk.

## License

This project is licensed under the [MIT License](LICENSE).
