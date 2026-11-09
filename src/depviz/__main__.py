import argparse
import sys
from dataclasses import asdict
from enum import IntEnum
from pathlib import Path

from .config import ProjectError, read_config
from .graph import (
    build_graph,
    has_cycle,
    label,
    read_fixture,
    reverse_dependencies,
)
from .registry import Registry


class Stage(IntEnum):
    CONFIG = 1
    DIRECT = 2
    GRAPH = 3
    REVERSE = 4


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Практическая № 2, вариант 3"
    )
    parser.add_argument(
        "--config", type=Path, default=Path("examples/is-odd.csv")
    )
    parser.add_argument(
        "--stage", type=int, choices=tuple(Stage), default=Stage.GRAPH
    )
    parser.add_argument(
        "--target", help="Искомый пакет этапа 4: имя или имя@версия"
    )
    parser.add_argument(
        "--transitive", action="store_true", help="Все обратные зависимости"
    )
    args = parser.parse_args()
    if args.stage != Stage.REVERSE and (
        args.target is not None or args.transitive
    ):
        parser.error("--target и --transitive доступны на этапе 4")
    return args


def show_config(config):
    for key, value in asdict(config).items():
        display = str(value).lower() if isinstance(value, bool) else value
        print(f"{key}={display}")


def show_direct(config, root):
    if config.test_mode:
        raise ProjectError("Для этапа 2 нужен адрес npm Registry.")
    dependencies = Registry(config.repository).dependencies(root)
    print(f"Прямые зависимости {label(root)}:")
    for name, spec in sorted(dependencies.items()):
        print(f"  {name}: {spec}")
    if not dependencies:
        print("  (нет)")


def load_graph(config, root, stage):
    if not config.test_mode:
        return build_graph(root, Registry(config.repository).neighbors)
    fixture = read_fixture(config.repository)
    if root not in fixture:
        raise ProjectError(f"Тестовый пакет {label(root)} не найден.")
    if stage == Stage.REVERSE:
        return fixture
    return build_graph(root, fixture.__getitem__)


def show_graph(graph):
    print("Граф в порядке BFS:")
    for node, children in graph.items():
        names = ", ".join(map(label, children)) or "(нет)"
        print(f"  {label(node)} -> {names}")
    print(f"Цикл: {'да' if has_cycle(graph) else 'нет'}")


def show_reverse(graph, query, transitive):
    targets = [node for node in graph if query in {node[0], label(node)}]
    if not targets:
        raise ProjectError(f"Пакет {query!r} отсутствует в области поиска.")
    for target in targets:
        direct = reverse_dependencies(graph, target)
        print(f"Прямые обратные зависимости {label(target)}:")
        print("  " + (", ".join(map(label, direct)) or "(нет)"))
        if transitive:
            parents = reverse_dependencies(graph, target, transitive=True)
            print("Все обратные зависимости в порядке BFS:")
            print("  " + (", ".join(map(label, parents)) or "(нет)"))


def main():
    args = parse_arguments()
    try:
        config = read_config(args.config)
        if args.stage == Stage.CONFIG:
            show_config(config)
            return 0

        root = (config.package, config.version)
        if args.stage == Stage.DIRECT:
            show_direct(config, root)
            return 0

        graph = load_graph(config, root, args.stage)
        if args.stage == Stage.REVERSE:
            show_reverse(graph, args.target or label(root), args.transitive)
        else:
            show_graph(graph)
    except ProjectError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
