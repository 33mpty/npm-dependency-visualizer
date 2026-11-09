"""Выбор версии для обычных диапазонов npm SemVer."""
import operator
import re

from .config import NUMBER, VERSION

VERSION_PARTS = 3

PART = rf"(?:{NUMBER}|[xX*])"
PARTIAL = re.compile(rf"{PART}(?:\.{PART}){{0,2}}")
COMPARATORS = {
    "=": operator.eq, ">": operator.gt, ">=": operator.ge,
    "<": operator.lt, "<=": operator.le,
}


def version_key(version):
    main, _, suffix = version.split("+", 1)[0].partition("-")
    numbers = tuple(int(part) for part in main.split("."))
    prerelease = tuple(
        (0, int(part)) if part.isdigit() else (1, part)
        for part in suffix.split(".")
    ) if suffix else ()
    return (*numbers, not suffix, prerelease)


def parse_partial(value):
    value = value.removeprefix("v")
    if VERSION.fullmatch(value):
        return version_key(value), VERSION_PARTS
    if not PARTIAL.fullmatch(value):
        raise ValueError(f"неподдерживаемая спецификация {value!r}")
    parts = []
    for part in value.split("."):
        if part in {"*", "x", "X"}:
            break
        parts.append(int(part))
    return tuple((parts + [0, 0, 0])[:3]) + (True, ()), len(parts)


def upper_bound(key, index):
    numbers = list(key[:3])
    numbers[index] += 1
    numbers[index + 1:] = [0] * (2 - index)
    return (*numbers, False, ((0, 0),))


def expand(prefix, value):
    key, size = parse_partial(value)
    if not size:
        if prefix in {"<", ">"}:
            return [("<", (0, 0, 0, False, ((0, 0),)))]
        return []
    if prefix in {"^", "~"}:
        index = min(size - 1, 1)
        if prefix == "^":
            index = next((i for i in range(size) if key[i]), size - 1)
        return [(">=", key), ("<", upper_bound(key, index))]
    if size == VERSION_PARTS:
        return [(prefix, key)]
    return expand_partial(prefix, key, size)


def expand_partial(prefix, key, size):
    upper = upper_bound(key, size - 1)
    if prefix == "=":
        return [(">=", key), ("<", upper)]
    if prefix == ">":
        return [(">=", (*upper[:3], True, ()))]
    if prefix == "<=":
        return [("<", upper)]
    if prefix == "<":
        return [("<", (*key[:3], False, ((0, 0),)))]
    return [(prefix, key)]


def comparator_set(clause):
    hyphen = re.fullmatch(r"(\S+)\s+-\s+(\S+)", clause)
    if hyphen:
        low, high = hyphen.groups()
        return expand(">=", low) + expand("<=", high)
    clause = re.sub(r"([<>=~^]+)\s+", r"\1", clause)
    clause = clause.replace("~>", "~")
    checks = []
    for token in clause.split():
        match = re.fullmatch(r"(<=|>=|[<>=~^])?(.+)", token)
        prefix, value = match.groups()
        checks.extend(expand(prefix or "=", value))
    return checks


def matches(key, checks):
    """Проверить ограничения диапазона с учётом prerelease."""
    prerelease_allowed = key[3] or any(
        not bound[3] and key[:3] == bound[:3]
        for _, bound in checks
    )
    return prerelease_allowed and all(
        COMPARATORS[op](key, bound) for op, bound in checks
    )


def max_satisfying(versions, spec):
    clauses = [comparator_set(part.strip()) for part in spec.split("||")]

    candidates = (
        (version_key(version), version)
        for version in versions if VERSION.fullmatch(version)
    )
    return max(
        ((key, version) for key, version in candidates
         if any(matches(key, checks) for checks in clauses)),
        default=(None, None),
    )[1]
