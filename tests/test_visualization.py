import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as element_tree
from pathlib import Path
from unittest.mock import patch

from src.depviz.graph import build_graph, read_fixture
from src.depviz.visualize import ascii_lines, render_graph, to_dot


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def cli(*args):
    return subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "src.depviz", *args],
        cwd=ROOT, capture_output=True, encoding="utf-8",
    )


def node(name):
    return name, "1.0.0"


class VisualizationTests(unittest.TestCase):
    def fixture(self, name):
        return read_fixture(EXAMPLES / f"{name}.json")

    def test_dot_preserves_isolated_node(self):
        graph = self.fixture("isolated")
        dot = to_dot(graph, node("A"))
        self.assertIn('"A@1.0.0"', dot)
        self.assertNotIn("->", dot)

    def test_dot_only_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            result = cli("--config", str(EXAMPLES / "cycle.csv"), "--dot-only",
                         "--output-dir", directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("[cycle]", result.stdout)
            dot = Path(directory) / "A-1.0.0.dot"
            self.assertIn('"C@1.0.0" -> "A@1.0.0"', dot.read_text())

    @unittest.skipUnless(shutil.which("dot"), "Graphviz не установлен")
    @patch("src.depviz.visualize.webbrowser.open")
    def test_svg_and_open_flag(self, browser):
        with tempfile.TemporaryDirectory() as directory:
            browser.return_value = True
            _, svg = render_graph(
                self.fixture("diamond"), node("A"), Path(directory),
                open_image=True,
            )
            root = element_tree.parse(svg).getroot()
            self.assertTrue(root.tag.endswith("}svg"))
            browser.assert_called_once_with(svg.resolve().as_uri())

    def test_ascii_cycle_and_shared_dependency(self):
        for fixture, marker in (("cycle", "[cycle]"), ("diamond", "[seen]")):
            with self.subTest(fixture=fixture):
                graph = build_graph(
                    node("A"), self.fixture(fixture).__getitem__
                )
                self.assertIn(marker, "\n".join(ascii_lines(graph, node("A"))))
