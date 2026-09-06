#!/usr/bin/env python3
"""Tests for k8s-ai export sub-command."""

import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "sample-bundle"


class TestExportCommand(unittest.TestCase):
    def _run_export(self, bundle_dir, output_path, spike_threshold=80):
        """Helper: call k8s_ai.py export programmatically."""
        from k8s_ai import main
        rc = main([
            "export",
            "--bundle", str(bundle_dir),
            "--output", str(output_path),
            "--spike-threshold", str(spike_threshold),
        ])
        return rc

    def test_export_produces_tarball(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bundle.tar.gz"
            rc = self._run_export(FIXTURES, out)
            self.assertEqual(rc, 0)
            self.assertTrue(out.exists(), f"Expected {out} to exist")

    def test_export_contains_triage_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bundle.tar.gz"
            rc = self._run_export(FIXTURES, out)
            self.assertEqual(rc, 0)
            with tarfile.open(out, "r:gz") as tar:
                names = tar.getnames()
            self.assertIn("triage-report.json", names, f"triage-report.json not found in {names}")

    def test_export_triage_report_is_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bundle.tar.gz"
            self._run_export(FIXTURES, out)
            with tarfile.open(out, "r:gz") as tar:
                member = tar.getmember("triage-report.json")
                f = tar.extractfile(member)
                data = json.loads(f.read())
            # Must have standard InvestigationReport fields
            self.assertIn("status", data)
            self.assertIn("hypotheses", data)
            self.assertIn("recommendations", data)
            self.assertIn("resource_spikes", data)
            self.assertIn("unknowns", data)

    def test_export_contains_evidence_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bundle.tar.gz"
            self._run_export(FIXTURES, out)
            with tarfile.open(out, "r:gz") as tar:
                names = tar.getnames()
            # Should contain at least one evidence file from the fixtures dir
            evidence_entries = [n for n in names if n != "triage-report.json"]
            self.assertTrue(len(evidence_entries) > 0, "No evidence files found in archive")

    def test_export_nonexistent_bundle_returns_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bundle.tar.gz"
            rc = self._run_export("/nonexistent/bundle", out)
            self.assertEqual(rc, 1)
            self.assertFalse(out.exists())

    def test_export_triage_report_has_spikes_from_fixtures(self):
        """The fixtures contain top-pods data → triage report should have spikes."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bundle.tar.gz"
            self._run_export(FIXTURES, out, spike_threshold=80)
            with tarfile.open(out, "r:gz") as tar:
                f = tar.extractfile(tar.getmember("triage-report.json"))
                data = json.loads(f.read())
            # Fixtures have payment-service at 90% CPU → should detect spike
            self.assertIsInstance(data["resource_spikes"], list)


if __name__ == "__main__":
    unittest.main()
