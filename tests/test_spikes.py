#!/usr/bin/env python3
"""Tests for resource spike detection in k8s_ai_core.investigation."""

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from k8s_ai_core.investigation import (  # noqa: E402
    DEFAULT_SPIKE_THRESHOLD,
    _parse_cpu_millicores,
    _parse_memory_bytes,
    _pct,
    detect_spikes,
)

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "sample-bundle"


class TestParseUnits(unittest.TestCase):
    def test_cpu_millicores_m(self):
        self.assertAlmostEqual(_parse_cpu_millicores("450m"), 450.0)

    def test_cpu_millicores_cores(self):
        self.assertAlmostEqual(_parse_cpu_millicores("2"), 2000.0)

    def test_cpu_millicores_invalid(self):
        self.assertIsNone(_parse_cpu_millicores("bad"))

    def test_memory_bytes_mi(self):
        self.assertAlmostEqual(_parse_memory_bytes("1800Mi"), 1800 * 1024 ** 2)

    def test_memory_bytes_gi(self):
        self.assertAlmostEqual(_parse_memory_bytes("2Gi"), 2 * 1024 ** 3)

    def test_memory_bytes_invalid(self):
        self.assertIsNone(_parse_memory_bytes("bad"))


class TestPct(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(_pct(450, 500), 90)

    def test_zero_limit(self):
        self.assertIsNone(_pct(100, 0))

    def test_none_used(self):
        self.assertIsNone(_pct(None, 500))

    def test_caps_at_100(self):
        self.assertEqual(_pct(600, 500), 100)


class TestDetectSpikes(unittest.TestCase):
    def test_detects_memory_spike_with_fixtures(self):
        """payment-service uses 1800Mi / 2Gi limit = 87.9% → MEDIUM spike."""
        spikes = detect_spikes(FIXTURES, threshold=80)
        mem_spikes = [s for s in spikes if s.resource == "memory" and "payment" in s.pod]
        self.assertTrue(len(mem_spikes) >= 1, f"Expected memory spike for payment-service, got: {spikes}")
        self.assertIn(mem_spikes[0].severity, ("MEDIUM", "HIGH"))

    def test_detects_cpu_spike_with_fixtures(self):
        """payment-service uses 450m / 500m limit = 90% → HIGH spike."""
        spikes = detect_spikes(FIXTURES, threshold=80)
        cpu_spikes = [s for s in spikes if s.resource == "cpu" and "payment" in s.pod]
        self.assertTrue(len(cpu_spikes) >= 1, f"Expected CPU spike for payment-service, got: {spikes}")
        self.assertEqual(cpu_spikes[0].severity, "HIGH")

    def test_threshold_filtering(self):
        """With threshold=100, no spikes should be returned."""
        spikes = detect_spikes(FIXTURES, threshold=100)
        self.assertEqual(spikes, [])

    def test_no_top_files_returns_empty(self):
        """Bundle without top files should return no spikes."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "pods.txt").write_text("NAMESPACE  NAME  READY  STATUS\n")
            spikes = detect_spikes(p, threshold=80)
            self.assertEqual(spikes, [])

    def test_spike_fields_present(self):
        """Each spike has all required fields."""
        spikes = detect_spikes(FIXTURES, threshold=80)
        for s in spikes:
            self.assertTrue(s.namespace)
            self.assertTrue(s.pod)
            self.assertTrue(s.container)
            self.assertIn(s.resource, ("cpu", "memory"))
            self.assertIsInstance(s.usage_pct, int)
            self.assertIn(s.severity, ("MEDIUM", "HIGH"))


class TestInvestigateBundleWithSpikes(unittest.TestCase):
    def test_spikes_in_report(self):
        """investigate_bundle() should attach spike results to the report."""
        from k8s_ai_core import investigate_bundle
        report = investigate_bundle(str(FIXTURES), spike_threshold=80)
        self.assertIsInstance(report.resource_spikes, list)

    def test_status_elevated_for_high_spike(self):
        """Status should be CRITICAL when a HIGH spike exists alongside hypotheses."""
        from k8s_ai_core import investigate_bundle
        report = investigate_bundle(str(FIXTURES), spike_threshold=80)
        # payment-service CPU is 90% → HIGH severity → CRITICAL status
        if any(s.severity == "HIGH" for s in report.resource_spikes):
            self.assertEqual(report.status, "CRITICAL")


if __name__ == "__main__":
    unittest.main()
