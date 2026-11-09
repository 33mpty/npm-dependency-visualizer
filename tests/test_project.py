import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as element_tree
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from src.depviz.config import ProjectError, read_config
from src.depviz.graph import (
    build_graph,
    has_cycle,
    read_fixture,
    reverse_dependencies,
)
from src.depviz.registry import Registry
from src.depviz.semver import max_satisfying
from src.depviz.visualize import ascii_lines, render_graph, to_dot

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def node(name):
    return name, "1.0.0"


def cli(*args):
    return subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "src.depviz", *args],
        cwd=ROOT, capture_output=True, encoding="utf-8",
    )


class ConfigTests(unittest.TestCase):
    def test_config_relative_fixture(self):
        config = read_config(EXAMPLES / "cycle.csv")
        self.assertEqual(Path(config.repository), EXAMPLES / "cycle.json")
        self.assertTrue(config.test_mode)

    def test_invalid_fields(self):
        baseline = (EXAMPLES / "is-odd.csv").read_text()
        cases = {
            "package": ("is-odd", "broken package"),
            "repository": (
                "https://registry.npmjs.org", "file:///tmp/metadata"
            ),
            "test_mode": ("false", "maybe"),
            "version": ("3.0.1", "^3.0.1"),
            "ascii_tree": ("true", "yes"),
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csv"
            for field, (old, bad) in cases.items():
                with self.subTest(field=field):
                    data = baseline.replace(f"{field},{old}", f"{field},{bad}")
                    path.write_text(data)
                    result = cli("--stage", "1", "--config", str(path))
                    self.assertEqual(result.returncode, 2)
                    self.assertIn(field, result.stderr)

    def test_malformed_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csv"
            for data in (
                "package,is-odd\n",
                "key,value\npackage,a\npackage,b\n",
                'key,value\npackage,"unclosed\n',
                "key,value\n",
            ):
                with self.subTest(data=data):
                    path.write_text(data)
                    with self.assertRaises(ProjectError):
                        read_config(path)

    def test_stage_one(self):
        result = cli("--stage", "1")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(result.stdout.splitlines()), 5)
        self.assertIn("version=3.0.1", result.stdout)


class RegistryTests(unittest.TestCase):
    @patch("src.depviz.registry.urlopen")
    def test_version_scoped_url_and_cache(self, request):
        request.return_value = io.BytesIO(json.dumps({"versions": {
            "1.0.0": {
                "dependencies": {"old": "^1.0.0"},
                "devDependencies": {"dev": "*"},
            },
            "2.0.0": {"dependencies": {"new": "~2.0.0"}},
        }}).encode())
        registry = Registry("https://example.invalid/")
        self.assertEqual(
            registry.dependencies(("@team/app", "1.0.0")), {"old": "^1.0.0"}
        )
        self.assertEqual(
            registry.dependencies(("@team/app", "2.0.0")), {"new": "~2.0.0"}
        )
        with self.assertRaisesRegex(ProjectError, "3.0.0"):
            registry.dependencies(("@team/app", "3.0.0"))
        request.assert_called_once()
        self.assertEqual(
            request.call_args.args[0].full_url,
            "https://example.invalid/@team%2Fapp",
        )

    @patch("src.depviz.registry.urlopen")
    def test_registry_http_error(self, request):
        request.side_effect = HTTPError(
            "https://example.invalid", 404, "missing", {}, None
        )
        with self.assertRaisesRegex(ProjectError, "404"):
            Registry("https://example.invalid").dependencies(node("a"))

    def test_semver_ranges(self):
        versions = [
            "0.2.5", "0.3.0", "1.2.3", "1.3.2", "1.10.0",
            "2.0.0-beta.2", "2.0.0-beta.10", "2.0.0",
        ]
        for spec, expected in {
            "^0.2.0": "0.2.5", "~1.3": "1.3.2", "1.x": "1.10.0",
            "1.2 - 1.3": "1.3.2", ">= 1.2.0 <2 || 0.3": "1.10.0",
            ">=2.0.0-beta.2 <2.0.0": "2.0.0-beta.10",
            "^1": "1.10.0", "3.x": None, "*": "2.0.0",
        }.items():
            with self.subTest(spec=spec):
                self.assertEqual(max_satisfying(versions, spec), expected)
        with self.assertRaises(ValueError):
            max_satisfying(versions, "git+https://example.invalid/a")


class GraphTests(unittest.TestCase):
    def fixture(self, name):
        return read_fixture(EXAMPLES / f"{name}.json")

    def test_diamond_and_shared_dependency(self):
        fixture = self.fixture("diamond")
        graph = build_graph(node("A"), fixture.__getitem__)
        self.assertEqual(list(graph), list(map(node, "ABCD")))
        self.assertFalse(has_cycle(graph))
        self.assertIn("[seen]", "\n".join(ascii_lines(graph, node("A"))))

    def test_cycle_and_reverse(self):
        fixture = self.fixture("cycle")
        graph = build_graph(node("A"), fixture.__getitem__)
        self.assertEqual(list(graph), list(map(node, "ABCD")))
        self.assertTrue(has_cycle(graph))
        self.assertIn(node("A"), graph[node("C")])
        self.assertIn("[cycle]", "\n".join(ascii_lines(graph, node("A"))))
        self.assertEqual(
            reverse_dependencies(graph, node("A"), transitive=True),
            (node("C"), node("B")),
        )

    def test_reverse_can_include_disconnected_parent(self):
        graph = self.fixture("diamond")
        self.assertEqual(
            reverse_dependencies(graph, node("D")), tuple(map(node, "BCE"))
        )
        self.assertEqual(
            reverse_dependencies(graph, node("D"), transitive=True),
            tuple(map(node, "BCEA")),
        )
        self.assertEqual(reverse_dependencies(graph, node("A")), ())

    def test_long_graph_without_recursion(self):
        length = 1500
        graph = build_graph(0, lambda n: [n + 1] if n < length else [])
        self.assertEqual(len(graph), length + 1)
        self.assertFalse(has_cycle(graph))
        parents = reverse_dependencies(graph, length, transitive=True)
        self.assertEqual(len(parents), length)

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


if __name__ == "__main__":
    unittest.main()
