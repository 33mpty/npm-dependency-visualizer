import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from src.depviz.config import ProjectError
from src.depviz.registry import Registry


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
            Registry("https://example.invalid").dependencies(("a", "1.0.0"))
