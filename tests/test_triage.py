#!/usr/bin/env python3
"""Tests for k8s-ai triage sub-command (JSON output and report structure)."""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "sample-bundle"


class TestTriageCommand(unittest.TestCase):
    def _triage_json(self, bundle_dir, extra_args=None):
        """Run triage --json and return parsed output dict."""
        from k8s_ai import main
        argv = ["triage", "--bundle", str(bundle_dir), "--json"] + (extra_args or [])
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(argv)
        output = buf.getvalue().strip()
        return rc, json.loads(output)

    def test_triage_json_exits_zero_on_fixture_bundle(self):
        rc, data = self._triage_json(FIXTURES)
        self.assertEqual(rc, 0, f"Expected rc=0, got rc={rc}")

    def test_triage_json_has_required_fields(self):
        _, data = self._triage_json(FIXTURES)
        for field in ("status", "question", "bundle", "hypotheses", "recommendations",
                      "resource_spikes", "unknowns", "evidence"):
            self.assertIn(field, data, f"Missing field '{field}' in triage output")

    def test_triage_json_hypotheses_are_list(self):
        _, data = self._triage_json(FIXTURES)
        self.assertIsInstance(data["hypotheses"], list)

    def test_triage_json_resource_spikes_are_list(self):
        _, data = self._triage_json(FIXTURES)
        self.assertIsInstance(data["resource_spikes"], list)

    def test_triage_json_recommendations_have_required_fields(self):
        _, data = self._triage_json(FIXTURES)
        for rec in data["recommendations"]:
            for field in ("action", "reason", "risk", "verification"):
                self.assertIn(field, rec, f"Recommendation missing field: {field}")

    def test_triage_json_spike_threshold_filters(self):
        """At threshold=100, no spikes should appear in report."""
        _, data = self._triage_json(FIXTURES, ["--spike-threshold", "100"])
        self.assertEqual(data["resource_spikes"], [])

    def test_triage_nonexistent_bundle_exits_2(self):
        from k8s_ai import main
        rc = main(["triage", "--bundle", "/nonexistent/bundle", "--json"])
        self.assertEqual(rc, 2)

    def test_triage_human_output_contains_hypotheses(self):
        """Human-readable output (non-JSON) should mention hypotheses."""
        from k8s_ai import main
        buf = io.StringIO()
        with redirect_stdout(buf):
            main(["triage", "--bundle", str(FIXTURES)])
        output = buf.getvalue()
        self.assertIn("HYPOTHESES", output)

    def test_triage_notify_dry_run(self):
        """--notify-dry-run should print payload without network calls."""
        from k8s_ai import main
        buf = io.StringIO()
        with redirect_stdout(buf):
            main([
                "triage", "--bundle", str(FIXTURES), "--json",
                "--notify-target", "slack",
                "--notify-webhook", "https://hooks.example.com",
                "--notify-dry-run",
            ])
        output = buf.getvalue()
        self.assertIn("[dry-run]", output)

    def test_triage_no_notification_on_clean_bundle(self):
        """A bundle with no findings should not attempt to send a notification."""
        with tempfile.TemporaryDirectory() as tmp:
            # Empty bundle — no signals, no spikes
            p = Path(tmp)
            (p / "empty.txt").write_text("nothing to see here\n")
            from k8s_ai import main
            with patch("notify.send_alert") as mock_send:
                main([
                    "triage", "--bundle", str(p), "--json",
                    "--notify-target", "slack",
                    "--notify-webhook", "https://hooks.example.com",
                ])
                mock_send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
