"""Независимая проверка трёх примеров через npm ls в каталоге temp."""
import json
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from src.depviz.config import ProjectError, read_config
from src.depviz.graph import build_graph, label
from src.depviz.registry import Registry

EXAMPLES = ("is-odd", "is-even", "escape-string-regexp")
PROJECT = Path(__file__).resolve().parents[1]
OMIT = ["--omit=dev", "--omit=optional", "--omit=peer"]


def npm_tree(root, npm, registry):
    with TemporaryDirectory(prefix="depviz-npm-") as directory:
        cwd = Path(directory)
        manifest = {
            "name": "depviz-check", "version": "1.0.0", "private": True
        }
        (cwd / "package.json").write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )
        subprocess.run(
            [npm, "install", "--ignore-scripts", "--no-audit", "--no-fund",
             "--save-exact", *OMIT,
             "--registry", registry, label(root)],
            cwd=cwd, check=True, capture_output=True, text=True, timeout=120,
        )
        listing = subprocess.run(
            [npm, "ls", "--all", "--json", *OMIT],
            cwd=cwd, check=True, capture_output=True, text=True, timeout=60,
        )
    return json.loads(listing.stdout)["dependencies"][root[0]]


def npm_graph(root, tree):
    nodes, edges = {root}, set()
    stack = [(root, tree)]
    while stack:
        parent, entry = stack.pop()
        for name, info in entry.get("dependencies", {}).items():
            child = (name, info["version"])
            nodes.add(child)
            edges.add((parent, child))
            stack.append((child, info))
    return nodes, edges


def describe_edges(edges):
    return ", ".join(
        f"{label(parent)} -> {label(child)}" for parent, child in sorted(edges)
    )


def describe_nodes(nodes):
    return ", ".join(map(label, sorted(nodes)))


def show_differences(nodes, edges, npm_nodes, npm_edges):
    differences = (
        ("Вершины только Python", describe_nodes(nodes - npm_nodes)),
        ("Вершины только npm", describe_nodes(npm_nodes - nodes)),
        ("Рёбра только Python", describe_edges(edges - npm_edges)),
        ("Рёбра только npm", describe_edges(npm_edges - edges)),
    )
    for title, details in differences:
        print(f"  {title}: {details or '-'}")


def compare_example(name, npm):
    config = read_config(PROJECT / "examples" / f"{name}.csv")
    root = (name, config.version)
    graph = build_graph(root, Registry(config.repository).neighbors)
    nodes = set(graph)
    edges = {
        (parent, child)
        for parent, children in graph.items()
        for child in children
    }
    tree = npm_tree(root, npm, config.repository)
    npm_nodes, npm_edges = npm_graph(root, tree)
    equal = nodes == npm_nodes and edges == npm_edges
    verdict = "совпадение" if equal else "расхождение"
    print(
        f"{label(root)}: Python {len(nodes)} вершин / {len(edges)} рёбер; "
        f"npm {len(npm_nodes)} / {len(npm_edges)}; {verdict}"
    )
    if not equal:
        show_differences(nodes, edges, npm_nodes, npm_edges)
    return equal


def main():
    npm = shutil.which("npm")
    if not npm:
        print("npm не найден в PATH.")
        return 2
    try:
        results = [compare_example(name, npm) for name in EXAMPLES]
    except subprocess.CalledProcessError as exc:
        print(f"Ошибка npm: {exc.stderr.strip() or exc}")
        return 2
    except (
        ProjectError, OSError, ValueError, KeyError, subprocess.TimeoutExpired
    ) as exc:
        print(f"Ошибка сравнения: {exc}")
        return 2
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
