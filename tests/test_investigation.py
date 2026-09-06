import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from k8s_ai_core import investigate_bundle


class TestInvestigation(unittest.TestCase):
    def test_missing_bundle_is_explicitly_unavailable(self):
        report = investigate_bundle("/tmp/k8s-ai-missing-bundle")
        self.assertEqual("UNAVAILABLE", report.status)
        self.assertTrue(report.unknowns)

    def test_oom_evidence_produces_high_confidence_hypothesis(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            (bundle / "pods.txt").write_text(
                "payments checkout-api Running OOMKilled restartCount=14\n",
                encoding="utf-8",
            )
            report = investigate_bundle(str(bundle), "Why is checkout-api crashing?")

        self.assertEqual("ATTENTION", report.status)
        self.assertEqual("OOMKilled", report.hypotheses[0].title)
        self.assertEqual("HIGH", report.hypotheses[0].confidence)
        self.assertTrue(report.recommendations[0].requires_approval)
        self.assertEqual("pods.txt", report.evidence[0].source)

    def test_json_contract_is_serializable(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            (bundle / "events.txt").write_text(
                "Warning FailedScheduling insufficient cpu\n",
                encoding="utf-8",
            )
            payload = investigate_bundle(str(bundle)).to_dict()

        encoded = json.dumps(payload)
        self.assertIn("FailedScheduling", encoded)
        self.assertIn("unknowns", payload)

    def test_empty_bundle_reports_unknown_instead_of_guessing(self):
        with tempfile.TemporaryDirectory() as directory:
            report = investigate_bundle(directory)

        self.assertEqual("NO_SIGNAL", report.status)
        self.assertEqual([], report.hypotheses)
        self.assertTrue(report.unknowns)


if __name__ == "__main__":
    unittest.main()
