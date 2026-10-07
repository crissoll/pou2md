from __future__ import annotations
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from .model.declaration import PouDeclaration
from .model.flow_graph import FlowGraph
from .parser.declaration import DeclarationParser
from .parser.nwl_parser import NWLParser
from .parser.cfc_parser import CFCParser
from .parser.st_parser import STParser
from .writer.markdown import MarkdownWriter


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
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

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

            with open(out_path, "w", encoding="utf-8") as f:
                f.write(md_output)

        return md_output, out_path

    def convert_directory(
        self,
        input_dir: Path | str,
        output_dir: Path | str | None = None,
        recursive: bool = False,
        unified: bool = False,
        unified_filename: str = "unified.md",
    ) -> tuple[list[Path], str | None]:
        """
        Convert all .TcPOU files in a directory.

        Parameters:
            input_dir: Root directory to scan for .TcPOU files.
            output_dir: Destination directory or file path for outputs.
            recursive: If True, search subdirectories and save flat names as 'foldera--folderb--file.md'.
            unified: If True, combine all converted POUs into a single Markdown document.
            unified_filename: Default filename if output_dir is a directory when unified=True.

        Returns:
            A tuple of (written_file_paths, unified_markdown_text).
        """
        in_dir = Path(input_dir)
        pattern = "**/*.TcPOU" if recursive else "*.TcPOU"
        pou_files = sorted(in_dir.glob(pattern))

        if unified:
            merged_sections: list[str] = []
            for pou_file in pou_files:
                md_text, _ = self.convert_file(pou_file)
                merged_sections.append(md_text.rstrip())

            unified_text = "\n\n---\n\n".join(merged_sections) + "\n"
            written_files: list[Path] = []

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

            return written_files, unified_text

        written_files: list[Path] = []
        for pou_file in pou_files:
            if recursive:
                rel = pou_file.relative_to(in_dir)
                if rel.parent.parts:
                    parts = list(rel.parent.parts) + [pou_file.stem]
                    custom_filename = "--".join(parts) + ".md"
                else:
                    custom_filename = f"{pou_file.stem}.md"
            else:
                custom_filename = f"{pou_file.stem}.md"

            _, out_path = self.convert_file(
                pou_file,
                output_dir=output_dir,
                custom_filename=custom_filename,
            )
            if out_path:
                written_files.append(out_path)

        return written_files, None
