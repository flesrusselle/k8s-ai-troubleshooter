import unittest
import yaml
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

class TestCommands(unittest.TestCase):
    def test_command_catalogs(self):
        cmd_dir = REPO_ROOT / "commands"
        allowed_safety = ["SAFE_READ", "SAFE_DIAGNOSTIC", "HUMAN_APPROVAL_REQUIRED", "DESTRUCTIVE"]
        
        for name in ["kubectl.yaml", "helm.yaml", "kustomize.yaml"]:
            file_path = cmd_dir / name
            self.assertTrue(file_path.exists(), f"Command catalog missing: {name}")
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                self.assertIn("catalog", data)
                self.assertIn("commands", data)
                for cmd in data["commands"]:
                    self.assertIn("name", cmd)
                    self.assertIn("command", cmd)
                    self.assertIn("safety", cmd)
                    self.assertIn(cmd["safety"], allowed_safety, f"Invalid safety classification: {cmd['safety']}")

if __name__ == "__main__":
    unittest.main()
