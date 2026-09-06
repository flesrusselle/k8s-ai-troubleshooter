#!/usr/bin/env python3
"""Tests for scripts/notify.py multi-target webhook dispatcher."""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from notify import (  # noqa: E402
    SUPPORTED_TARGETS,
    build_payload,
    resolve_url,
    send_alert,
)

SAMPLE_SESSION = {
    "session_id": "test-uuid-1234",
    "timestamp": "2026-09-06T05:00:00Z",
    "source": "collect",
    "scope": "all-namespaces",
    "unhealthy_pods": 3,
    "runbook": "pod-crashloop",
    "confidence": "high",
}

SAMPLE_REPORT = {
    "status": "CRITICAL",
    "question": "Investigate the evidence bundle",
    "bundle": "/tmp/test-bundle",
    "hypotheses": [
        {
            "title": "OOMKilled",
            "confidence": "HIGH",
            "rationale": "Container exceeded memory limit.",
            "evidence": [],
        }
    ],
    "recommendations": [],
    "unknowns": [],
    "resource_spikes": [
        {
            "namespace": "production",
            "pod": "payment-service-xxx",
            "container": "payment",
            "resource": "memory",
            "usage_raw": "1800Mi",
            "limit_raw": "2Gi",
            "usage_pct": 88,
            "severity": "MEDIUM",
        }
    ],
}


class TestSupportedTargets(unittest.TestCase):
    def test_all_targets_present(self):
        self.assertIn("slack", SUPPORTED_TARGETS)
        self.assertIn("pagerduty", SUPPORTED_TARGETS)
        self.assertIn("googlechat", SUPPORTED_TARGETS)


class TestBuildPayload(unittest.TestCase):
    def test_slack_payload_structure(self):
        payload = build_payload(SAMPLE_SESSION, SAMPLE_REPORT, target="slack")
        self.assertIn("attachments", payload)
        blocks = payload["attachments"][0]["blocks"]
        # Should have at least header + section + hypotheses + spikes + divider
        self.assertGreaterEqual(len(blocks), 3)

    def test_pagerduty_payload_structure(self):
        payload = build_payload(SAMPLE_SESSION, SAMPLE_REPORT, target="pagerduty")
        self.assertIn("event_action", payload)
        self.assertEqual(payload["event_action"], "trigger")
        self.assertIn("payload", payload)
        self.assertIn("custom_details", payload["payload"])

    def test_googlechat_payload_structure(self):
        payload = build_payload(SAMPLE_SESSION, SAMPLE_REPORT, target="googlechat")
        self.assertIn("cardsV2", payload)
        self.assertTrue(len(payload["cardsV2"]) > 0)

    def test_unsupported_target_raises(self):
        with self.assertRaises(ValueError):
            build_payload(SAMPLE_SESSION, SAMPLE_REPORT, target="teams")

    def test_none_report_handled(self):
        """build_payload should not crash when report is None."""
        for target in SUPPORTED_TARGETS:
            payload = build_payload(SAMPLE_SESSION, None, target=target)
            self.assertIsInstance(payload, dict)

    def test_slack_includes_hypothesis_title(self):
        payload = build_payload(SAMPLE_SESSION, SAMPLE_REPORT, target="slack")
        raw = json.dumps(payload)
        self.assertIn("OOMKilled", raw)

    def test_slack_includes_spike(self):
        payload = build_payload(SAMPLE_SESSION, SAMPLE_REPORT, target="slack")
        raw = json.dumps(payload)
        self.assertIn("payment", raw)

    def test_pagerduty_severity_critical(self):
        payload = build_payload(SAMPLE_SESSION, SAMPLE_REPORT, target="pagerduty")
        self.assertEqual(payload["payload"]["severity"], "critical")

    def test_pagerduty_dedup_key_has_session_id(self):
        payload = build_payload(SAMPLE_SESSION, SAMPLE_REPORT, target="pagerduty")
        self.assertIn(SAMPLE_SESSION["session_id"], payload["dedup_key"])


class TestResolveUrl(unittest.TestCase):
    def test_explicit_url_returned(self):
        self.assertEqual(resolve_url("slack", "https://hooks.example.com"), "https://hooks.example.com")

    def test_env_var_fallback(self):
        import os
        with patch.dict(os.environ, {"K8S_AI_NOTIFY_SLACK_URL": "https://env-slack.example.com"}):
            url = resolve_url("slack")
        self.assertEqual(url, "https://env-slack.example.com")

    def test_returns_none_when_unset(self):
        import os
        env = {k: v for k, v in os.environ.items() if "K8S_AI_NOTIFY" not in k}
        with patch.dict(os.environ, env, clear=True):
            result = resolve_url("slack")
        self.assertFalse(result)


class TestSendAlert(unittest.TestCase):
    def test_dry_run_prints_payload(self):
        payload = build_payload(SAMPLE_SESSION, SAMPLE_REPORT, target="slack")
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            result = send_alert("slack", "https://unused.example.com", payload, dry_run=True)
        self.assertTrue(result)
        output = buf.getvalue()
        self.assertIn("[dry-run]", output)
        self.assertIn("slack", output)

    def test_dry_run_does_not_call_network(self):
        payload = {"text": "test"}
        with patch("urllib.request.urlopen") as mock_open:
            send_alert("slack", "https://hooks.example.com", payload, dry_run=True)
            mock_open.assert_not_called()

    def test_http_error_raises_runtime(self):
        import urllib.error
        payload = {"text": "test"}
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.status = 200
        with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
            url="https://x", code=400, msg="Bad Request", hdrs=None, fp=None
        )):
            with self.assertRaises(RuntimeError):
                send_alert("slack", "https://hooks.example.com", payload, dry_run=False)


if __name__ == "__main__":
    unittest.main()
