from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .converter import TcPOUConverter
from .manifest import clean_stale_outputs, manifest_path, save_manifest


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        })


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
        help="Recursively scan subdirectories for .TcPOU files.",
    )
    parser.add_argument(
        "-u",
        "--unified",
        action="store_true",
        help="Save all converted POUs into a single Markdown file.",
    )
    parser.add_argument(
        "--single-folder",
        action="store_true",
        help="Also save individual Markdown files (the default unless --unified is used alone).",
    )
    parser.add_argument(
        "--copy-folder-structure",
        action="store_true",
        help="Save individual Markdown files using the input folder structure instead of flattened names.",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PATTERN",
        help="Exclude matching filename or relative path pattern; may be repeated.",
    )
    parser.add_argument("--poll-interval", type=float, default=1.0, help="Watcher polling interval in seconds.")
    parser.add_argument("--debounce-delay", type=float, default=0.25, help="Delay after a detected change in seconds.")
    parser.add_argument("--retry-count", type=int, default=3, help="Conversion attempts after a transient save failure.")
    parser.add_argument("--retry-delay", type=float, default=0.5, help="Delay between conversion attempts in seconds.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable diagnostic logging.")
    parser.add_argument("--quiet", action="store_true", help="Suppress normal status messages.")
    parser.add_argument("--log-format", choices=("text", "json"), default="text", help="Logging output format.")
    parser.add_argument("--dry-run", action="store_true", help="Show planned outputs without writing files.")
    parser.add_argument("--clean", action="store_true", help="Remove stale outputs recorded by the manifest.")
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

    if args.quiet and args.verbose:
        parser.error("--quiet and --verbose cannot be used together")
    if args.poll_interval <= 0 or args.debounce_delay < 0 or args.retry_count < 1 or args.retry_delay < 0:
        parser.error("watch timing values must be positive (debounce/retry delays may be zero)")
    if input_path.is_dir() and args.copy_folder_structure and not args.recursive:
        parser.error("--copy-folder-structure requires --recursive for directory input")
    if input_path.is_dir() and args.stdout and not args.unified:
        parser.error("--stdout for directory input requires --unified")
    if args.clean and not args.output:
        parser.error("--clean requires --output")
    if args.clean and not input_path.is_dir():
        parser.error("--clean requires directory input")
    if args.dry_run and args.watch:
        parser.error("--dry-run cannot be combined with --watch")

    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter() if args.log_format == "json" else logging.Formatter("[%(levelname)s] %(message)s"))
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else (logging.ERROR if args.quiet else logging.INFO),
        handlers=[handler],
    )

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
            single_folder=(not args.unified) or args.single_folder or args.copy_folder_structure,
            copy_folder_structure=args.copy_folder_structure,
            to_stdout=args.stdout or (input_path.is_file() and not args.output),
            poll_interval=args.poll_interval,
            debounce_delay=args.debounce_delay,
            retry_count=args.retry_count,
            retry_delay=args.retry_delay,
            exclude=tuple(args.exclude),
            quiet=args.quiet,
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
        elif not args.quiet:
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
            single_folder=(not args.unified) or args.single_folder or args.copy_folder_structure,
            copy_folder_structure=args.copy_folder_structure,
            exclude=tuple(args.exclude),
            dry_run=args.dry_run,
        )

        if args.output:
            manifest = manifest_path(args.output)
            current_outputs = set(written)
            stale = clean_stale_outputs(manifest, current_outputs, dry_run=args.dry_run) if args.clean else []
            if args.clean and not args.dry_run or not args.dry_run:
                save_manifest(manifest, current_outputs)
        else:
            stale = []

        if args.dry_run:
            for path in written:
                print(f"Would generate: {path}")
            for path in stale:
                print(f"Would remove: {path}")

        if args.stdout or (args.unified and not args.output):
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
            if unified_text:
                print(unified_text)
        elif not args.quiet:
            if args.unified and written:
                print(f"Generated {len(written)} output file(s).")
            else:
                print(f"Converted {len(written)} POU file(s) to '{args.output}'.")
                for f in written:
                    print(f"  - {f.name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
