import json
from collections import deque
from pathlib import Path

from .config import ProjectError, TEST_PACKAGE, VERSION


def label(node):
    return f"{node[0]}@{node[1]}"


def breadth_first(start, neighbors):
    queue = deque([start])
    seen = {start}
    while queue:
        node = queue.popleft()
        yield node
        for child in neighbors(node):
            if child not in seen:
                seen.add(child)
                queue.append(child)


def build_graph(root, neighbors):
    graph = {}

    def record_edges(node):
        graph[node] = tuple(neighbors(node))
        return graph[node]

    for _ in breadth_first(root, record_edges):
        pass
    return graph


def has_cycle(graph):
    """Удалить вершины с нулевой входящей степенью. Цикл останется."""
    incoming = dict.fromkeys(graph, 0)
    for children in graph.values():
        for child in children:
            incoming[child] += 1
    queue = deque(node for node, degree in incoming.items() if not degree)
    removed = 0
    while queue:
        node = queue.popleft()
        removed += 1
        for child in graph[node]:
            incoming[child] -= 1
            if not incoming[child]:
                queue.append(child)
    return removed != len(graph)


def load_fixture_data(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ProjectError(
            f"Ошибка чтения тестового репозитория: {exc}"
        ) from exc
    if not isinstance(data, dict) or not VERSION.fullmatch(
        str(data.get("version", ""))
    ):
        raise ProjectError(
            "Тестовый репозиторий: нужно поле version с версией SemVer."
        )
    version = data["version"]
    packages = data.get("packages")
    if not isinstance(packages, dict) or not packages:
        raise ProjectError(
            "Тестовый репозиторий: нужен непустой объект packages."
        )
    return version, packages


def fixture_children(name, children, packages):
    if not TEST_PACKAGE.fullmatch(name) or not isinstance(children, list):
        raise ProjectError(f"Некорректное описание тестового пакета {name!r}.")
    if any(
        not isinstance(child, str) or child not in packages
        for child in children
    ):
        raise ProjectError(
            f"{name}: зависимость отсутствует в тестовом репозитории."
        )
    return dict.fromkeys(children)


def read_fixture(path):
    version, packages = load_fixture_data(path)
    graph = {}
    for name, children in packages.items():
        dependencies = fixture_children(name, children, packages)
        graph[name, version] = tuple(
            (child, version) for child in dependencies
        )
    return graph
