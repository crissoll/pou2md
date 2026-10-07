from __future__ import annotations
import argparse
import sys
from pathlib import Path
from .converter import TcPOUConverter


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tcpou_to_mermaid",
        description="Convert TwinCAT 3 .TcPOU files into Mermaid diagrams in Markdown.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=".",
        help="Path to a .TcPOU file or directory containing .TcPOU files (default: .).",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output directory or output file path (e.g. -o output/ or -o unified.md).",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively scan subdirectories for .TcPOU files and save them as 'foldera--folderb--file.md'.",
    )
    parser.add_argument(
        "-u",
        "--unified",
        action="store_true",
        help="Save all converted POUs into a single Markdown file.",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print Markdown output to stdout instead of saving to a file.",
    )
    parser.add_argument(
        "--curve",
        choices=["step", "stepAfter", "linear", "basis", "none"],
        default="step",
        help="Mermaid flowchart curve style (default: 'step' for straight orthogonal lines with horizontal node entry).",
    )
    parser.add_argument(
        "--no-bifurcate",
        dest="bifurcate",
        action="store_false",
        default=True,
        help="Disable bifurcation junction nodes (draw separate wires instead of a branching junction).",
    )
    parser.add_argument(
        "--repeat-inputs",
        action="store_true",
        default=False,
        help="Repeat input variable blocks per connection in CFC (avoids long cross-diagram wires).",
    )
    parser.add_argument(
        "-w",
        "--watch",
        action="store_true",
        help="Watch input file or directory for changes and automatically re-convert.",
    )

    args = parser.parse_args()
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: Path '{input_path}' does not exist.", file=sys.stderr)
        return 1

    curve_setting = None if args.curve == "none" else args.curve
    converter = TcPOUConverter(
        curve=curve_setting,
        bifurcate=args.bifurcate,
        repeat_inputs=args.repeat_inputs,
    )

    if args.watch:
        if input_path.is_dir() and not args.output and not args.stdout:
            print(
                "Error: Please specify an output target with -o / --output, or use --stdout.",
                file=sys.stderr,
            )
            return 1
        from .watcher import start_watcher

        return start_watcher(
            input_path=input_path,
            converter=converter,
            output=args.output,
            recursive=args.recursive,
            unified=args.unified,
            to_stdout=args.stdout or (input_path.is_file() and not args.output),
        )

    if input_path.is_file():
        md_text, out_file = converter.convert_file(
            input_path,
            output_dir=args.output if not args.stdout else None,
        )
        if args.stdout or not args.output:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
            print(md_text)
        else:
            print(f"Generated: {out_file}")

    elif input_path.is_dir():
        if not args.output and not args.stdout:
            print(
                "Error: Please specify an output target with -o / --output, or use --stdout.",
                file=sys.stderr,
            )
            return 1

        written, unified_text = converter.convert_directory(
            input_dir=input_path,
            output_dir=args.output if not args.stdout else None,
            recursive=args.recursive,
            unified=args.unified,
        )

        if args.stdout or (args.unified and not args.output):
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
            if unified_text:
                print(unified_text)
        else:
            if args.unified and written:
                print(f"Unified {len(written)} file into: {written[0]}")
            else:
                print(f"Converted {len(written)} POU file(s) to '{args.output}'.")
                for f in written:
                    print(f"  - {f.name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
