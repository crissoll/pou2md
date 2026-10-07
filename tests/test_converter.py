"""
Unit and integration tests for the POU to Markdown converter.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from pou2md.converter import TcPOUConverter
from pou2md.errors import TcPOUParseError
from pou2md.manifest import load_manifest, manifest_path, save_manifest
from pou2md.parser.cfc_parser import CFCParser
from pou2md.parser.declaration import DeclarationParser
from pou2md.parser.nwl_parser import NWLParser
from pou2md.parser.st_parser import STParser
from pou2md.renderer.class_diagram import ClassDiagramRenderer

BASE_DIR = Path(__file__).resolve().parent.parent
POU_DIR = BASE_DIR / "tests" / "fixtures" / "pous"
EXPECTED_DIR = BASE_DIR / "tests" / "expected"


class TestDeclarationParser(unittest.TestCase):
    """Tests for IEC 61131-3 CDATA declaration parsing."""

    def setUp(self):
        self.parser = DeclarationParser()
        self.renderer = ClassDiagramRenderer()

    def test_fb_blinker_declaration(self):
        tree = ET.parse(POU_DIR / "FB_Blinker.TcPOU")
        decl_text = tree.find(".//Declaration").text or ""
        decl = self.parser.parse(decl_text)

        self.assertEqual(decl.name, "FB_Blinker")
        self.assertEqual(decl.pou_type, "FUNCTION_BLOCK")

        inputs = decl.get_variables_by_group("VAR_INPUT")
        self.assertEqual([v.name for v in inputs], ["bStart", "tSignalTimerOn", "tSignalTimerOff"])
        self.assertEqual([v.data_type for v in inputs], ["BOOL", "TIME", "TIME"])

        outputs = decl.get_variables_by_group("VAR_OUTPUT")
        self.assertEqual([v.name for v in outputs], ["bOut"])
        self.assertEqual(outputs[0].data_type, "BOOL")

        internal = decl.get_variables_by_group("VAR")
        self.assertEqual([v.name for v in internal], ["fbTimerA", "fbTimerB"])

        rendered = self.renderer.render(decl)
        self.assertIn("class FB_Blinker {", rendered)
        self.assertIn("<<FUNCTION_BLOCK>>", rendered)
        self.assertIn("+BOOL bStart", rendered)
        self.assertIn("-BOOL bOut", rendered)
        self.assertIn("TON fbTimerA", rendered)

    def test_main_declaration(self):
        tree = ET.parse(POU_DIR / "MAIN.TcPOU")
        decl_text = tree.find(".//Declaration").text or ""
        decl = self.parser.parse(decl_text)

        self.assertEqual(decl.name, "MAIN")
        self.assertEqual(decl.pou_type, "PROGRAM")

        internal = decl.get_variables_by_group("VAR")
        self.assertEqual(len(internal), 2)
        self.assertEqual(internal[0].name, "fHysteresis")
        self.assertEqual(internal[0].initial_value, "1")
        self.assertEqual(internal[1].name, "fbSR")

        rendered = self.renderer.render(decl)
        self.assertIn("REAL fHysteresis = 1", rendered)
        self.assertIn("SR fbSR", rendered)

    def test_signals_declaration(self):
        tree = ET.parse(POU_DIR / "Signals.TcPOU")
        decl_text = tree.find(".//Declaration").text or ""
        decl = self.parser.parse(decl_text)

        self.assertEqual(decl.name, "Signals")
        self.assertEqual(decl.pou_type, "PROGRAM")
        internal = decl.get_variables_by_group("VAR")
        self.assertEqual([v.name for v in internal], ["fbTimer1", "fbTimer2", "fbBlinker"])

    def test_simulation_declaration(self):
        tree = ET.parse(POU_DIR / "Simulation.TcPOU")
        decl_text = tree.find(".//Declaration").text or ""
        decl = self.parser.parse(decl_text)

        self.assertEqual(decl.name, "Simulation")
        self.assertEqual(decl.pou_type, "PROGRAM")
        internal = decl.get_variables_by_group("VAR")
        self.assertEqual(len(internal), 9)

        # Check initial values
        by_name = {v.name: v for v in internal}
        self.assertEqual(by_name["tCooling"].initial_value, "T#500MS")
        self.assertEqual(by_name["tEnvironment"].initial_value, "T#2S")
        self.assertEqual(by_name["tEnvironmentDoorOpen"].initial_value, "T#1s")


class TestNWLParser(unittest.TestCase):
    """Tests for NWL parser (FBD and LD)."""

    def setUp(self):
        self.parser = NWLParser()

    def test_fb_blinker_fbd(self):
        tree = ET.parse(POU_DIR / "FB_Blinker.TcPOU")
        nwl_elem = tree.find(".//Implementation/NWL")
        graph = self.parser.parse(nwl_elem)

        self.assertEqual(graph.language, "FBD")
        self.assertEqual(len(graph.networks), 1)

        net = graph.networks[0]
        node_ids = {n.id for n in net.nodes}
        self.assertIn("bStart", node_ids)
        self.assertIn("fbTimerBQ", node_ids)
        self.assertIn("TON_A", node_ids)
        self.assertIn("TON_B", node_ids)
        self.assertIn("AND1", node_ids)

        # Check negated edge
        dotted_edges = [e for e in net.edges if e.style == "dotted"]
        self.assertTrue(len(dotted_edges) > 0)
        self.assertEqual(dotted_edges[0].source_id, "fbTimerBQ")
        self.assertEqual(dotted_edges[0].target_id, "AND1")
        self.assertIn("negated", dotted_edges[0].label or "")

    def test_signals_ld(self):
        tree = ET.parse(POU_DIR / "Signals.TcPOU")
        nwl_elem = tree.find(".//Implementation/NWL")
        graph = self.parser.parse(nwl_elem)

        self.assertEqual(graph.language, "LD")
        self.assertEqual(len(graph.networks), 3)

        # Network 1: Jump label and coil
        n1 = graph.networks[0]
        n1_nodes = {n.id: n for n in n1.nodes}
        self.assertIn("N1_DoorIsOpen", n1_nodes)
        self.assertEqual(n1_nodes["N1_DoorIsOpen"].node_type, "LABEL")
        self.assertIn("DoorIsOpen", n1_nodes["N1_DoorIsOpen"].label)

        # Network 2: TON -> Blinker -> series contact -> Signal
        n2 = graph.networks[1]
        n2_nodes = {n.id for n in n2.nodes}
        self.assertIn("N2_TON", n2_nodes)
        self.assertIn("N2_Blinker", n2_nodes)
        self.assertIn("N2_fbTimer2Q", n2_nodes)

        # Network 3: DoorIsOpen label
        n3 = graph.networks[2]
        self.assertEqual(n3.label, "DoorIsOpen")


class TestCFCParser(unittest.TestCase):
    """Tests for CFC parser."""

    def setUp(self):
        self.parser = CFCParser()

    def test_main_cfc(self):
        tree = ET.parse(POU_DIR / "MAIN.TcPOU")
        cfc_elem = tree.find(".//Implementation/CFC")
        graph = self.parser.parse(cfc_elem)

        self.assertEqual(graph.language, "CFC")
        node_ids = {n.id for n in graph.nodes}

        # Check input variables
        self.assertIn("fTempActual", node_ids)
        self.assertIn("fTempSet", node_ids)
        self.assertIn("fHysteresis", node_ids)

        # Check operators and FBs
        self.assertIn("ADD1", node_ids)
        self.assertIn("SUB1", node_ids)
        self.assertIn("GT1", node_ids)
        self.assertIn("LT1", node_ids)
        self.assertIn("SR1", node_ids)
        self.assertIn("Signals", node_ids)

        # Check output variable
        self.assertIn("bCompressor", node_ids)

        # Check connections
        edge_tuples = [(e.source_id, e.target_id, e.label) for e in graph.edges]
        self.assertIn(("GT1", "SR1", "SET1"), edge_tuples)
        self.assertIn(("LT1", "SR1", "RESET"), edge_tuples)
        self.assertIn(("SR1", "bCompressor", "Q1"), edge_tuples)


class TestSTParser(unittest.TestCase):
    """Tests for Structured Text parser."""

    def setUp(self):
        self.parser = STParser()

    def test_simulation_st(self):
        tree = ET.parse(POU_DIR / "Simulation.TcPOU")
        st_elem = tree.find(".//Implementation/ST")
        graph = self.parser.parse(st_elem)

        self.assertEqual(graph.language, "ST")
        self.assertIsNotNone(graph.st_code)
        self.assertIn("IF GVL_VAR.bCompressor THEN", graph.st_code)
        self.assertIn("nCounter := nCounter+1;", graph.st_code)


class TestEndToEndConverter(unittest.TestCase):
    """End-to-end integration tests."""

    def setUp(self):
        self.converter = TcPOUConverter()

    def test_convert_all_four_pous(self):
        pous = ["FB_Blinker", "MAIN", "Signals", "Simulation"]
        for pou_name in pous:
            pou_path = POU_DIR / f"{pou_name}.TcPOU"
            md_text, _ = self.converter.convert_file(pou_path)

            # Basic assertions
            self.assertIn(f"# {pou_name}", md_text)
            self.assertIn("classDiagram", md_text)

            if pou_name == "Simulation":
                self.assertIn("```iecst", md_text)
            else:
                self.assertIn("flowchart LR", md_text)

    def test_cli_execution(self):
        # Run CLI with --stdout on FB_Blinker.TcPOU
        cmd = [
            sys.executable,
            "-m",
            "pou2md",
            str(POU_DIR / "FB_Blinker.TcPOU"),
            "--stdout",
        ]
        result = subprocess.run(
            cmd,
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("# FB_Blinker", result.stdout)
        self.assertIn("flowchart LR", result.stdout)

    def test_recursive_conversion_naming(self):
        import shutil
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            nested_dir = tmp_path / "foldera" / "folderb"
            nested_dir.mkdir(parents=True)
            shutil.copy(POU_DIR / "Simulation.TcPOU", nested_dir / "SubSim.TcPOU")

            out_dir = tmp_path / "output"
            written, _ = self.converter.convert_directory(
                input_dir=tmp_path,
                output_dir=out_dir,
                recursive=True,
            )

            self.assertEqual(len(written), 1)
            self.assertEqual(written[0].name, "foldera--folderb--SubSim.md")

    def test_unified_conversion(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = Path(tmp_dir) / "merged.md"
            written, unified_text = self.converter.convert_directory(
                input_dir=POU_DIR,
                output_dir=out_file,
                unified=True,
            )

            self.assertEqual(len(written), 1)
            self.assertEqual(written[0], out_file)
            self.assertTrue(out_file.exists())
            self.assertIn("# FB_Blinker", unified_text)
            self.assertIn("# MAIN", unified_text)
            self.assertIn("# Signals", unified_text)
            self.assertIn("# Simulation", unified_text)
            self.assertIn("---", unified_text)

    def test_unified_and_individual_conversion(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir) / "output"
            written, unified_text = self.converter.convert_directory(
                input_dir=POU_DIR,
                output_dir=out_dir,
                unified=True,
                single_folder=True,
            )

            self.assertEqual(len(written), 5)
            self.assertEqual(written[0], out_dir / "unified.md")
            self.assertTrue((out_dir / "FB_Blinker.md").exists())
            self.assertIn("# MAIN", unified_text)

    def test_recursive_copy_folder_structure(self):
        import shutil
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            nested_dir = tmp_path / "foldera" / "folderb"
            nested_dir.mkdir(parents=True)
            shutil.copy(POU_DIR / "Simulation.TcPOU", nested_dir / "SubSim.TcPOU")

            out_dir = tmp_path / "output"
            written, _ = self.converter.convert_directory(
                input_dir=tmp_path,
                output_dir=out_dir,
                recursive=True,
                copy_folder_structure=True,
            )

            self.assertEqual(written, [out_dir / "foldera" / "folderb" / "SubSim.md"])

    def test_recursive_conversion_excludes_output_directory_inside_input(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            input_dir = Path(tmp_dir)
            output_dir = input_dir / "pou2md-output"
            output_dir.mkdir()
            (input_dir / "Keep.TcPOU").write_text(
                (POU_DIR / "Simulation.TcPOU").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (output_dir / "AlreadyGenerated.TcPOU").write_text(
                (POU_DIR / "Simulation.TcPOU").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            written, _ = self.converter.convert_directory(
                input_dir=input_dir,
                output_dir=output_dir,
                recursive=True,
            )

            self.assertEqual(written, [output_dir / "Keep.md"])

    def test_exclude_patterns_and_atomic_output(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            input_dir = Path(tmp_dir) / "input"
            output_dir = Path(tmp_dir) / "output"
            input_dir.mkdir()
            (input_dir / "Keep.TcPOU").write_text(
                (POU_DIR / "Simulation.TcPOU").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (input_dir / "Skip.TcPOU").write_text(
                (POU_DIR / "Simulation.TcPOU").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            written, _ = self.converter.convert_directory(
                input_dir=input_dir,
                output_dir=output_dir,
                exclude=("Skip.TcPOU",),
            )

            self.assertEqual(written, [output_dir / "Keep.md"])
            self.assertFalse(list(output_dir.glob("*.tmp")))

    def test_dry_run_does_not_write_outputs(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "output"
            written, _ = self.converter.convert_directory(
                input_dir=POU_DIR,
                output_dir=output_dir,
                dry_run=True,
            )

            self.assertEqual(len(written), 4)
            self.assertFalse(output_dir.exists())

    def test_parse_error_contains_filename_and_location(self):
        with self.assertRaisesRegex(TcPOUParseError, r"broken\.TcPOU.*line"):
            self.converter.convert_content("<TcPou><broken></TcPou>", "broken.TcPOU")

    def test_cli_config_and_version(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            config = Path(tmp_dir) / "pou2md.toml"
            output = Path(tmp_dir) / "docs"
            config.write_text(
                f'input = "{POU_DIR.as_posix()}"\n'
                f'output = "{output.as_posix()}"\n'
                "unified = true\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, "-m", "pou2md", "--config", str(config), "--quiet"],
                cwd=str(BASE_DIR),
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(result.returncode, 0)
            self.assertTrue((output / "unified.md").exists())

            version_result = subprocess.run(
                [sys.executable, "-m", "pou2md", "--version"],
                cwd=str(BASE_DIR),
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(version_result.returncode, 0)
            self.assertRegex(version_result.stdout.strip(), r"\d+\.\d+\.\d+")

    def test_manifest_records_outputs_and_metadata(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir) / "output"
            written, _ = self.converter.convert_directory(
                input_dir=POU_DIR,
                output_dir=output_dir,
            )
            path = manifest_path(output_dir)
            save_manifest(path, written, metadata={"test": True})
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["metadata"]["test"], True)
            self.assertEqual(load_manifest(path), {item.resolve() for item in written})

    def test_cli_recursive_and_unified(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = Path(tmp_dir) / "all_pous.md"
            cmd = [
                sys.executable,
                "-m",
                "pou2md",
                str(BASE_DIR / "tests" / "fixtures"),
                "-r",
                "-u",
                "-o",
                str(out_file),
            ]
            result = subprocess.run(
                cmd,
                cwd=str(BASE_DIR),
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(result.returncode, 0)
            self.assertTrue(out_file.exists())
            content = out_file.read_text(encoding="utf-8")
            self.assertIn("# FB_Blinker", content)
            self.assertIn("# MAIN", content)

    def test_cli_default_input(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = Path(tmp_dir) / "all_pous.md"
            cmd = [
                sys.executable,
                "-m",
                "pou2md",
                "-r",
                "-u",
                "-o",
                str(out_file),
            ]
            result = subprocess.run(
                cmd,
                cwd=str(BASE_DIR / "tests" / "fixtures"),
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(result.returncode, 0)
            self.assertTrue(out_file.exists())
            content = out_file.read_text(encoding="utf-8")
            self.assertIn("# FB_Blinker", content)
            self.assertIn("# MAIN", content)

    def test_cli_default_output_directory(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            input_dir = Path(tmp_dir)
            (input_dir / "Example.TcPOU").write_text(
                (POU_DIR / "Simulation.TcPOU").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, "-m", "pou2md", str(input_dir)],
                cwd=str(input_dir),
                env={**os.environ, "PYTHONPATH": str(BASE_DIR)},
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertEqual(result.returncode, 0)
            self.assertTrue((input_dir / "pou2md-output" / "Example.md").exists())
            self.assertIn("excluded from scanning", result.stderr)

    def test_curve_and_bifurcation(self):
        # Test that stepAfter curve and bifurcation junction nodes are rendered
        conv = TcPOUConverter(curve="stepAfter", bifurcate=True)
        md_text, _ = conv.convert_file(POU_DIR / "FB_Blinker.TcPOU")
        self.assertIn("%%{ init: { 'flowchart': { 'curve': 'stepAfter' } } }%%", md_text)
        self.assertIn("J_TON_A_Q(( )):::junction", md_text)
        self.assertIn("classDef junction", md_text)

        # Test with bifurcate disabled
        conv_no_bif = TcPOUConverter(curve=None, bifurcate=False)
        md_no_bif, _ = conv_no_bif.convert_file(POU_DIR / "FB_Blinker.TcPOU")
        self.assertNotIn("classDef junction", md_no_bif)
        self.assertNotIn("%%{ init:", md_no_bif)

    def test_cfc_rank_alignment_and_repeat_inputs(self):
        # Default CFC conversion should include rank alignment ~~~ and step curve
        conv = TcPOUConverter()
        md_text, _ = conv.convert_file(POU_DIR / "MAIN.TcPOU")
        self.assertIn("%%{ init: { 'flowchart': { 'curve': 'step' } } }%%", md_text)
        self.assertIn("ADD1[\"ADD\"]", md_text)
        self.assertIn("ADD1 ~~~ SUB1", md_text)
        self.assertIn("GT1 ~~~ LT1", md_text)

        # With repeat_inputs=True
        conv_rep = TcPOUConverter(repeat_inputs=True)
        md_rep, _ = conv_rep.convert_file(POU_DIR / "MAIN.TcPOU")
        self.assertIn("fTempActual_1", md_rep)
        self.assertIn("fTempActual_2", md_rep)


if __name__ == "__main__":
    unittest.main()
