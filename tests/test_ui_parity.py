"""Tests for UI ↔ CLI parity and asset synchronization.

Verifies:
1. ui/mock-sessions.json adheres to InvestigationReport schema
2. ui/ files match helm/ files byte-for-byte
3. ui/index.html references all required parity components (hypotheses, spikes,
   recommendations, unknowns, alert targets, auto-refresh, bundle export)
"""

import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
UI_DIR = REPO_ROOT / "ui"
HELM_UI_DIR = REPO_ROOT / "helm" / "k8s-ai-troubleshooter" / "files" / "ui"


class TestUIPatternsAndSync(unittest.TestCase):
    def test_helm_ui_files_are_identical(self):
        """Every file in ui/ must match helm/k8s-ai-troubleshooter/files/ui/ byte-for-byte."""
        for filename in ["index.html", "index.css", "mock-sessions.json"]:
            ui_file = UI_DIR / filename
            helm_file = HELM_UI_DIR / filename
            self.assertTrue(ui_file.exists(), f"Missing {ui_file}")
            self.assertTrue(helm_file.exists(), f"Missing {helm_file}")
            self.assertEqual(
                ui_file.read_bytes(),
                helm_file.read_bytes(),
                f"Mismatch between {ui_file} and {helm_file}. Run sync command.",
            )

    def test_mock_sessions_schema(self):
        """mock-sessions.json entries must match InvestigationReport fields."""
        with open(UI_DIR / "mock-sessions.json", "r", encoding="utf-8") as f:
            sessions = json.load(f)

        self.assertIsInstance(sessions, list)
        self.assertGreater(len(sessions), 0)

        for s in sessions:
            self.assertIn("session_id", s)
            self.assertIn("timestamp", s)
            self.assertIn("source", s)

            # Hypotheses schema check
            if "hypotheses" in s and s["hypotheses"]:
                for h in s["hypotheses"]:
                    self.assertIn("title", h)
                    self.assertIn("confidence", h)
                    self.assertIn(h["confidence"], ("HIGH", "MEDIUM", "LOW"))
                    self.assertIn("rationale", h)
                    self.assertIn("evidence", h)
                    self.assertIsInstance(h["evidence"], list)

            # Resource spikes schema check
            if "resource_spikes" in s and s["resource_spikes"]:
                for sp in s["resource_spikes"]:
                    self.assertIn("namespace", sp)
                    self.assertIn("pod", sp)
                    self.assertIn("container", sp)
                    self.assertIn("resource", sp)
                    self.assertIn("usage_pct", sp)
                    self.assertIn("severity", sp)
                    self.assertIn(sp["severity"], ("HIGH", "MEDIUM"))

            # Recommendations schema check
            if "recommendations" in s and s["recommendations"]:
                for r in s["recommendations"]:
                    self.assertIn("action", r)
                    self.assertIn("reason", r)
                    self.assertIn("risk", r)
                    self.assertIn("verification", r)

    def test_ui_index_contains_parity_features(self):
        """index.html must include UI components for all 5 improvement areas."""
        content = (UI_DIR / "index.html").read_text(encoding="utf-8")

        # 1. Hypotheses & confidence
        self.assertIn("hypotheses", content)
        self.assertIn("CONFIDENCE", content)

        # 2. Resource spikes
        self.assertIn("resource_spikes", content)
        self.assertIn("badge-spike", content)

        # 3. Recommendations & risk
        self.assertIn("recommendations", content)
        self.assertIn("risk", content)
        self.assertIn("verification", content)

        # 4. Unknowns
        self.assertIn("unknowns", content)

        # 5. Multi-target alert dispatcher
        self.assertIn("alert-target", content)
        self.assertIn("slack", content)
        self.assertIn("pagerduty", content)
        self.assertIn("googlechat", content)
        self.assertIn("alert-dry-run", content)

        # 6. Auto-refresh
        self.assertIn("select-refresh", content)
        self.assertIn("handleRefreshChange", content)

        # 7. Bundle export download
        self.assertIn("btn-download-bundle", content)
        self.assertIn("downloadBundleTar", content)


if __name__ == "__main__":
    unittest.main()
