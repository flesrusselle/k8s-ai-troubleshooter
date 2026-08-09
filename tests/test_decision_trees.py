import unittest
import yaml
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

class TestDecisionTrees(unittest.TestCase):
    def test_decision_trees_validity(self):
        trees_dir = REPO_ROOT / "decision-trees"
        trees = list(trees_dir.glob("*.yaml"))
        self.assertGreaterEqual(len(trees), 5, "Should have at least 5 decision trees")
        
        for tree in trees:
            with open(tree, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                self.assertIn("id", data)
                self.assertIn("trigger", data)
                self.assertIn("steps", data)
                self.assertGreater(len(data["steps"]), 0)

if __name__ == "__main__":
    unittest.main()
