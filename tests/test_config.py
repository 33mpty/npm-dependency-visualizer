import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.depviz.config import ProjectError, read_config


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def cli(*args):
    return subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "src.depviz", *args],
        cwd=ROOT, capture_output=True, encoding="utf-8",
    )


class ConfigTests(unittest.TestCase):
    def test_invalid_fields(self):
        for path in sorted((EXAMPLES / "invalid").glob("*.csv")):
            field = path.stem.split("-", 1)[1]
            with self.subTest(field=field):
                result = cli("--stage", "1", "--config", str(path))
                self.assertEqual(result.returncode, 2)
                self.assertIn(field, result.stderr)

    def test_malformed_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csv"
            for data in (
                "package,is-odd\n",
                "key,value\npackage,a\npackage,b\n",
                'key,value\npackage,"unclosed\n',
                "key,value\n",
            ):
                with self.subTest(data=data):
                    path.write_text(data)
                    with self.assertRaises(ProjectError):
                        read_config(path)

    def test_stage_one(self):
        result = cli("--stage", "1", "--config", str(EXAMPLES / "is-odd.csv"))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(result.stdout.splitlines()), 5)
        self.assertIn("version=3.0.1", result.stdout)
