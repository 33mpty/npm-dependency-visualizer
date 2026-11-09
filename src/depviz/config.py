import csv
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

PACKAGE = re.compile(r"(?:@[a-z0-9][a-z0-9._~-]*/)?[a-z0-9][a-z0-9._~-]*")
CSV_HEADER = ["key", "value"]
TEST_PACKAGE = re.compile(r"[A-Z]+")
NUMBER = r"(?:0|[1-9][0-9]*)"
VERSION = re.compile(
    rf"{NUMBER}\.{NUMBER}\.{NUMBER}"
    r"(?:-(?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*)?"
    r"(?:\+[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*)?"
)


class ProjectError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    package: str
    repository: str
    test_mode: bool
    version: str
    ascii_tree: bool


def read_csv_fields(path):
    fields = {}
    allowed = Config.__dataclass_fields__
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = csv.reader(stream, strict=True)
            if next(rows, None) != CSV_HEADER:
                raise ProjectError("Заголовок CSV должен быть key,value.")
            for row in rows:
                if not row:
                    continue
                if len(row) != len(CSV_HEADER):
                    raise ProjectError(
                        f"CSV, строка {rows.line_num}: нужны два столбца."
                    )
                key, value = (cell.strip() for cell in row)
                if key not in allowed or key in fields:
                    raise ProjectError(
                        f"Неизвестный или повторный ключ: {key!r}."
                    )
                fields[key] = value
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ProjectError(f"Не удалось прочитать CSV {path}: {exc}") from exc

    missing = allowed.keys() - fields.keys()
    if missing:
        raise ProjectError(f"Не хватает ключей: {', '.join(sorted(missing))}.")
    return fields


def read_boolean(fields, key):
    value = fields[key].lower()
    if value not in {"true", "false"}:
        raise ProjectError(f"{key}: ожидается true или false.")
    return value == "true"


def valid_registry_url(repository):
    try:
        url = urlsplit(repository)
        _ = url.port
    except ValueError:
        return False
    return (
        url.scheme in {"http", "https"}
        and bool(url.hostname)
        and not (url.query or url.fragment or url.username or url.password)
        and not any(char.isspace() for char in repository)
    )


def read_repository(path, repository, test_mode):
    if test_mode:
        fixture = (path.parent / repository).resolve()
        if not fixture.is_file():
            raise ProjectError(f"repository: файл не найден: {fixture}")
        return str(fixture)
    if not valid_registry_url(repository):
        raise ProjectError("repository: нужен HTTP(S)-адрес npm Registry.")
    return repository


def read_config(path):
    fields = read_csv_fields(path)
    test_mode = read_boolean(fields, "test_mode")
    ascii_tree = read_boolean(fields, "ascii_tree")
    pattern = TEST_PACKAGE if test_mode else PACKAGE
    if not pattern.fullmatch(fields["package"]):
        raise ProjectError(
            "package: неверное имя пакета для выбранного режима."
        )
    if not VERSION.fullmatch(fields["version"]):
        raise ProjectError(
            "version: нужна точная версия SemVer, например 1.0.0."
        )
    repository = read_repository(path, fields["repository"], test_mode)
    return Config(
        fields["package"], repository, test_mode, fields["version"], ascii_tree
    )
