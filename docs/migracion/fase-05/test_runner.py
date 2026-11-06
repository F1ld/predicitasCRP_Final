"""Autopruebas stdlib del publicador; no requieren Docker, secretos o modelo."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from validar_ia import junit, verify, write


class RunnerTests(unittest.TestCase):
    def setUp(self):
        approved = Path(os.environ["LOCALAPPDATA"]) / "Temp/opencode"
        self.temp = tempfile.TemporaryDirectory(dir=approved)
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_exclusive_writer(self):
        path = self.root / "one.json"
        write(path, {"value": 1})
        with self.assertRaises(FileExistsError):
            write(path, {"value": 2})
        self.assertEqual(json.loads(path.read_text()), {"value": 1})

    def test_junit_measured_not_constant(self):
        path = self.root / "tests.xml"
        path.write_text('<testsuite><testcase classname="one" name="a"/><testcase classname="one" name="b"><failure/></testcase><testcase classname="one" name="c"><skipped/></testcase></testsuite>')
        self.assertEqual(junit(path), {"passed": 1, "failure": 1, "skipped": 1})

    def test_manifest_rejects_escape(self):
        write(self.root / "manifest.json", {"run_id": "ia-test", "files": [{"name": "../outside", "sha256": "0" * 64}]})
        with self.assertRaises(AssertionError):
            verify(self.root, "ia-test")


if __name__ == "__main__":
    unittest.main()
