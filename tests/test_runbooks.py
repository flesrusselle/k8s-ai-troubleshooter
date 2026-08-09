import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

class TestRunbooks(unittest.TestCase):
    def test_runbook_sections(self):
        runbooks_dir = REPO_ROOT / "runbooks"
        required_sections = [
            "## Purpose", "## Safety Level", "## Symptoms",
            "## Quick Diagnosis", "## Detailed Investigation",
            "## Decision Tree", "## Evidence to Collect", "## Root Cause Patterns",
            "## Remediation", "## Human Approval Required", "## Official Documentation"
        ]
        
        runbooks = list(runbooks_dir.rglob("*.md"))
        self.assertGreater(len(runbooks), 10, "Should have more than 10 runbooks")
        
        for rb in runbooks:
            content = rb.read_text(encoding="utf-8")
            for section in required_sections:
                self.assertIn(section, content, f"Runbook {rb.name} missing section '{section}'")

if __name__ == "__main__":
    unittest.main()
