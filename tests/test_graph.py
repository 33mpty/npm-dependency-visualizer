import unittest
from pathlib import Path

from src.depviz.graph import build_graph, has_cycle, read_fixture
from src.depviz.semver import max_satisfying


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def node(name):
    return name, "1.0.0"


class GraphTests(unittest.TestCase):
    def fixture(self, name):
        return read_fixture(EXAMPLES / f"{name}.json")

    def test_diamond_and_shared_dependency(self):
        fixture = self.fixture("diamond")
        graph = build_graph(node("A"), fixture.__getitem__)
        self.assertEqual(list(graph), list(map(node, "ABCD")))
        self.assertFalse(has_cycle(graph))

    def test_cycle(self):
        fixture = self.fixture("cycle")
        graph = build_graph(node("A"), fixture.__getitem__)
        self.assertEqual(list(graph), list(map(node, "ABCD")))
        self.assertTrue(has_cycle(graph))
        self.assertIn(node("A"), graph[node("C")])

    def test_long_graph_without_recursion(self):
        length = 1500
        graph = build_graph(0, lambda n: [n + 1] if n < length else [])
        self.assertEqual(len(graph), length + 1)
        self.assertFalse(has_cycle(graph))

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
