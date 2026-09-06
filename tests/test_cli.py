import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import k8s_ai


class TestCli(unittest.TestCase):
    def test_collection_rejects_short_aliases(self):
        with self.assertRaises(SystemExit) as raised:
            k8s_ai.build_parser().parse_args(["collect", "-n", "prod"])
        self.assertEqual(2, raised.exception.code)

    def test_safety_json_is_machine_readable(self):
        output = io.StringIO()
        with redirect_stdout(output):
            result = k8s_ai.main(["safety", "kubectl delete namespace prod", "--json"])

        payload = json.loads(output.getvalue())
        self.assertEqual(0, result)
        self.assertEqual("DESTRUCTIVE", payload["safety"])
        self.assertFalse(payload["automatic_execution_allowed"])

    def test_safety_text_is_human_readable(self):
        output = io.StringIO()
        with redirect_stdout(output):
            k8s_ai.main(["safety", "kubectl get pods -A"])

        self.assertIn("Safety: SAFE_READ", output.getvalue())
        self.assertIn("Automatic execution: yes", output.getvalue())

    def test_collect_delegates_existing_options(self):
        with patch.object(k8s_ai.collect, "main", return_value=0) as collect_main:
            result = k8s_ai.main([
                "collect", "--namespace", "prod", "--no-pods", "--dry-run",
            ])

        self.assertEqual(0, result)
        collect_main.assert_called_once_with([
            "--namespace", "prod", "--output", "evidence-bundle", "--timeout", "60",
            "--no-pods", "--dry-run",
        ])


if __name__ == "__main__":
    unittest.main()