import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .config import PACKAGE, VERSION, ProjectError
from .semver import max_satisfying


class Registry:
    def __init__(self, url):
        self.url = url.rstrip("/")
        self.cache = {}

    def metadata(self, name):
        if name not in self.cache:
            url = f"{self.url}/{quote(name, safe='@')}"
            headers = {"Accept": "application/vnd.npm.install-v1+json"}
            request = Request(url, headers=headers)
            try:
                with urlopen(request, timeout=15) as response:
                    data = json.load(response)
            except HTTPError as exc:
                raise ProjectError(
                    f"{name}: npm Registry вернул HTTP {exc.code}."
                ) from exc
            except (URLError, OSError, ValueError) as exc:
                raise ProjectError(
                    f"{name}: ошибка чтения npm Registry: {exc}"
                ) from exc
            if not isinstance(data, dict) or not isinstance(
                data.get("versions"), dict
            ):
                raise ProjectError(
                    f"{name}: в ответе реестра нет объекта versions."
                )
            self.cache[name] = data
        return self.cache[name]

    def dependencies(self, node):
        name, version = node
        entry = self.metadata(name)["versions"].get(version)
        if not isinstance(entry, dict):
            raise ProjectError(f"Версия {name}@{version} не найдена.")
        dependencies = entry.get("dependencies", {})
        if not isinstance(dependencies, dict) or any(
            not PACKAGE.fullmatch(key)
            or not isinstance(value, str)
            or not value.strip()
            for key, value in dependencies.items()
        ):
            raise ProjectError(
                f"{name}@{version}: неверный формат dependencies."
            )
        return dependencies

    def resolve(self, name, spec):
        data = self.metadata(name)
        versions = data["versions"]
        if spec in versions and VERSION.fullmatch(spec):
            return name, spec
        tags = data.get("dist-tags", {})
        tagged = tags.get(spec) if isinstance(tags, dict) else None
        if (
            isinstance(tagged, str)
            and tagged in versions
            and VERSION.fullmatch(tagged)
        ):
            return name, tagged
        try:
            version = max_satisfying(versions, spec)
        except ValueError as exc:
            raise ProjectError(f"{name}: {exc}.") from exc
        if version is None:
            raise ProjectError(f"{name}: нет версии для диапазона {spec!r}.")
        return name, version

    def neighbors(self, node):
        for name, spec in sorted(self.dependencies(node).items()):
            yield self.resolve(name, spec)
