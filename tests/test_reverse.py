import unittest
from pathlib import Path

from src.depviz.graph import read_fixture, reverse_dependencies


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def node(name):
    return name, "1.0.0"


class ReverseTests(unittest.TestCase):
    def fixture(self, name):
        return read_fixture(EXAMPLES / f"{name}.json")

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

    def test_reverse_through_cycle(self):
        graph = self.fixture("cycle")
        self.assertEqual(
            reverse_dependencies(graph, node("A"), transitive=True),
            (node("C"), node("B")),
        )

    def test_long_reverse_chain(self):
        graph = {index: (index + 1,) for index in range(1500)}
        graph[1500] = ()
        parents = reverse_dependencies(graph, 1500, transitive=True)
        self.assertEqual(parents, tuple(range(1499, -1, -1)))
