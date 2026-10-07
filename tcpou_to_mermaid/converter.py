from __future__ import annotations
import os
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from .model.declaration import PouDeclaration
from .model.flow_graph import FlowGraph
from .parser.declaration import DeclarationParser
from .parser.nwl_parser import NWLParser
from .parser.cfc_parser import CFCParser
from .parser.st_parser import STParser
from .writer.markdown import MarkdownWriter


def _read_file_with_retry(path: Path, max_retries: int = 3, delay: float = 0.1) -> str:
    """Read a file with retries to handle transient file locks during editor saves."""
    for attempt in range(max_retries):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except (PermissionError, OSError):
            if attempt == max_retries - 1:
                raise
            time.sleep(delay)
    return ""


class TcPOUConverter:
    """Orchestrator to convert TwinCAT 3 .TcPOU files into Mermaid Markdown documents."""

    def __init__(
        self,
        curve: str | None = "step",
        bifurcate: bool = True,
        repeat_inputs: bool = False,
    ):
        self.repeat_inputs = repeat_inputs
        self.declaration_parser = DeclarationParser()
        self.nwl_parser = NWLParser()
        self.cfc_parser = CFCParser()
        self.st_parser = STParser()
        self.markdown_writer = MarkdownWriter(curve=curve, bifurcate=bifurcate)

    def convert_content(self, xml_content: str, filename: str = "POU.TcPOU") -> str:
        """Parse XML string content and return generated Markdown text."""
        root = ET.fromstring(xml_content)

        # 1. Declaration
        decl_elem = root.find(".//Declaration")
        decl_text = decl_elem.text if decl_elem is not None else ""
        decl = self.declaration_parser.parse(decl_text or "")

        # 2. Implementation
        impl_elem = root.find(".//Implementation")
        graph: FlowGraph

        if impl_elem is not None:
            st_elem = impl_elem.find("./ST")
            nwl_elem = impl_elem.find("./NWL")
            cfc_elem = impl_elem.find("./CFC")

            if st_elem is not None:
                graph = self.st_parser.parse(st_elem)
            elif nwl_elem is not None:
                graph = self.nwl_parser.parse(nwl_elem)
            elif cfc_elem is not None:
                graph = self.cfc_parser.parse(
                    cfc_elem, repeat_inputs=self.repeat_inputs
                )
            else:
                graph = FlowGraph(language="UNKNOWN")
        else:
            graph = FlowGraph(language="NONE")

        # 3. Generate Markdown
        return self.markdown_writer.generate(decl, graph, filename)

    def convert_file(
        self,
        file_path: Path | str,
        output_dir: Path | str | None = None,
        custom_filename: str | None = None,
    ) -> tuple[str, Path | None]:
        """Convert a single .TcPOU file, optionally writing to an output directory."""
        path = Path(file_path)
        content = _read_file_with_retry(path)

        md_output = self.convert_content(content, filename=path.name)

        out_path: Path | None = None
        if output_dir:
            out_target = Path(output_dir)
            if out_target.suffix.lower() == ".md" and not out_target.is_dir():
                out_path = out_target
                out_path.parent.mkdir(parents=True, exist_ok=True)
            else:
                out_target.mkdir(parents=True, exist_ok=True)
                fname = custom_filename if custom_filename else f"{path.stem}.md"
                out_path = out_target / fname
                out_path.parent.mkdir(parents=True, exist_ok=True)

            with open(out_path, "w", encoding="utf-8") as f:
                f.write(md_output)

        return md_output, out_path

    def convert_directory(
        self,
        input_dir: Path | str,
        output_dir: Path | str | None = None,
        recursive: bool = False,
        unified: bool = False,
        single_folder: bool | None = None,
        copy_folder_structure: bool = False,
        unified_filename: str = "unified.md",
    ) -> tuple[list[Path], str | None]:
        """
        Convert all .TcPOU files in a directory.

        Parameters:
            input_dir: Root directory to scan for .TcPOU files.
            output_dir: Destination directory or file path for outputs.
            recursive: If True, search subdirectories.
            unified: If True, combine all converted POUs into a single Markdown document.
            single_folder: If True, write individual Markdown files.
            copy_folder_structure: If True, preserve source subdirectories for individual files.
            unified_filename: Default filename if output_dir is a directory when unified=True.

        Returns:
            A tuple of (written_file_paths, unified_markdown_text).
        """
        if single_folder is None:
            single_folder = not unified

        in_dir = Path(input_dir)
        candidates = in_dir.rglob("*") if recursive else in_dir.iterdir()
        pou_files = sorted(
            (path for path in candidates if path.is_file() and path.suffix.lower() == ".tcpou"),
            key=lambda path: str(path).lower(),
        )

        written_files: list[Path] = []
        unified_text: str | None = None

        if unified:
            merged_sections: list[str] = []
            for pou_file in pou_files:
                md_text, _ = self.convert_file(pou_file)
                merged_sections.append(md_text.rstrip())

            unified_text = "\n\n---\n\n".join(merged_sections) + "\n"

            if output_dir:
                out_target = Path(output_dir)
                if out_target.suffix.lower() == ".md":
                    out_path = out_target
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                else:
                    out_target.mkdir(parents=True, exist_ok=True)
                    out_path = out_target / unified_filename

                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(unified_text)
                written_files.append(out_path)

        if single_folder:
            individual_output = Path(output_dir) if output_dir else None
            if individual_output and individual_output.suffix.lower() == ".md":
                individual_output = individual_output.parent

            individual_files: list[Path] = []
            for pou_file in pou_files:
                if recursive and copy_folder_structure:
                    rel = pou_file.relative_to(in_dir)
                    custom_filename = str(rel.with_suffix(".md"))
                elif recursive:
                    rel = pou_file.relative_to(in_dir)
                    parts = list(rel.parent.parts) + [pou_file.stem]
                    custom_filename = "--".join(parts) + ".md"
                else:
                    custom_filename = f"{pou_file.stem}.md"

                _, out_path = self.convert_file(
                    pou_file,
                    output_dir=individual_output,
                    custom_filename=custom_filename,
                )
                if out_path:
                    individual_files.append(out_path)

            written_files.extend(individual_files)

        return written_files, unified_text
