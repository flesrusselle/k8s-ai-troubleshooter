import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

class TestSchemas(unittest.TestCase):
    def test_json_schemas_exist_and_load(self):
        schemas_dir = REPO_ROOT / "schemas"
        expected = ["runbook.schema.json", "decision-tree.schema.json", "command.schema.json"]
        for s in expected:
            file_path = schemas_dir / s
            self.assertTrue(file_path.exists(), f"Schema missing: {s}")
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.assertIn("$schema", data)
                self.assertIn("title", data)

if __name__ == "__main__":
    unittest.main()
