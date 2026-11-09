import json
import subprocess
import webbrowser

from .config import ProjectError
from .graph import label


def to_dot(graph, root):
    names = {
        node: json.dumps(label(node), ensure_ascii=False) for node in graph
    }
    lines = ["digraph dependencies {", "  rankdir=LR;", "  node [shape=box];"]
    for node, name in names.items():
        style = " [style=filled, fillcolor=lightblue]" if node == root else ""
        lines.append(f"  {name}{style};")
    for node, children in graph.items():
        for child in children:
            lines.append(f"  {names[node]} -> {names[child]};")
    return "\n".join(lines + ["}", ""])


def ascii_lines(graph, root):
    seen = set()
    ancestors = set()
    stack = [(root, "", "", False)]
    while stack:
        node, prefix, branch, leaving = stack.pop()
        if leaving:
            ancestors.remove(node)
            continue

        line = prefix + branch + label(node)
        if node in ancestors:
            yield line + " [cycle]"
            continue
        if node in seen:
            yield line + " [seen]"
            continue

        yield line
        seen.add(node)
        ancestors.add(node)
        stack.append((node, "", "", True))
        child_prefix = prefix + {"": "", "`-- ": "    ", "|-- ": "|   "}[branch]
        stack.extend(tree_children(graph[node], child_prefix))


def tree_children(children, prefix):
    if children:
        yield children[-1], prefix, "`-- ", False
        for child in reversed(children[:-1]):
            yield child, prefix, "|-- ", False


def render_graph(graph, root, output_dir, *, dot_only=False, open_image=False):
    stem = "-".join((root[0].replace("/", "-").removeprefix("@"), root[1]))
    dot = output_dir / f"{stem}.dot"
    svg = dot.with_suffix(".svg")
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        dot.write_text(to_dot(graph, root), encoding="utf-8")
        if dot_only:
            return dot, None
        result = subprocess.run(
            ["dot", "-Tsvg", str(dot)],
            capture_output=True,
            check=True,
            timeout=60,
        )
        svg.write_bytes(result.stdout)
    except FileNotFoundError as exc:
        if exc.filename == "dot":
            raise ProjectError(
                f"Graphviz dot не найден в PATH. DOT сохранён: {dot}"
            ) from exc
        raise ProjectError(f"Не удалось записать граф: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", errors="replace").strip()
        raise ProjectError(f"Graphviz завершился с ошибкой: {detail}") from exc
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProjectError(f"Ошибка визуализации: {exc}") from exc

    if open_image and not webbrowser.open(svg.resolve().as_uri()):
        raise ProjectError(
            f"Браузер не открылся. Откройте SVG вручную: {svg.resolve()}"
        )
    return dot, svg
