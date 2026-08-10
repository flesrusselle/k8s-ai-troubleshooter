import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import collect
from collect import (
    POD_PLAN,
    UnsafeCommand,
    assert_safe,
    build_plan,
    find_unhealthy_pods,
    write_capture,
)
from safety import SAFE_DIAGNOSTIC, SAFE_READ, classify


class TestCollectorCannotMutate(unittest.TestCase):
    """
    The collector's safety property is that it is structurally incapable of
    changing a cluster. These tests are the enforcement of that claim.
    """

    def test_every_planned_command_is_read_only(self):
        for scope in ({"namespace": "prod"}, {"all_namespaces": True}, {}):
            for name, command in build_plan(**scope):
                with self.subTest(command=command):
                    self.assertIn(
                        classify(command).safety, {SAFE_READ, SAFE_DIAGNOSTIC},
                        f"planned step {name!r} is not read-only: {command}",
                    )

    def test_every_per_pod_command_is_read_only(self):
        for name, template in POD_PLAN:
            command = template.format(pod="web-1", ns="prod")
            with self.subTest(command=command):
                self.assertIn(classify(command).safety, {SAFE_READ, SAFE_DIAGNOSTIC})

    def test_assert_safe_refuses_a_destructive_command(self):
        with self.assertRaises(UnsafeCommand):
            assert_safe("kubectl delete namespace prod")

    def test_assert_safe_refuses_an_approval_tier_command(self):
        with self.assertRaises(UnsafeCommand):
            assert_safe("kubectl rollout restart deployment/api -n prod")

    def test_assert_safe_refuses_a_chained_command_hiding_a_delete(self):
        with self.assertRaises(UnsafeCommand):
            assert_safe("kubectl get pods && kubectl delete ns prod")

    def test_run_command_refuses_before_executing(self):
        """The guard must sit in front of the subprocess, not after it."""
        with self.assertRaises(UnsafeCommand):
            collect.run_command("kubectl delete pod web-1 -n prod --force")


class TestPlanScoping(unittest.TestCase):
    def test_namespace_is_threaded_into_namespaced_commands(self):
        commands = [c for _, c in build_plan(namespace="payments")]
        self.assertTrue(any("get pods -n payments" in c for c in commands))

    def test_all_namespaces_flag_is_used(self):
        commands = [c for _, c in build_plan(all_namespaces=True)]
        self.assertTrue(any("--all-namespaces" in c for c in commands))

    def test_optional_steps_can_be_excluded(self):
        with_optional = [n for n, _ in build_plan(namespace="x", include_optional=True)]
        without = [n for n, _ in build_plan(namespace="x", include_optional=False)]
        self.assertIn("top-nodes", with_optional)
        self.assertNotIn("top-nodes", without)

    def test_plan_step_names_are_unique(self):
        names = [n for n, _ in build_plan(namespace="x")]
        self.assertEqual(len(names), len(set(names)))


class TestUnhealthyPodDetection(unittest.TestCase):
    def setUp(self):
        self._original = collect.run_command

    def tearDown(self):
        collect.run_command = self._original

    def _stub(self, output):
        collect.run_command = lambda command, timeout=60: (True, output)

    def test_detects_failing_states(self):
        self._stub(
            "web-1     0/1   CrashLoopBackOff   7    5m\n"
            "web-2     1/1   Running            0    5m\n"
            "job-x     0/1   Completed          0    1h\n"
            "img-1     0/1   ImagePullBackOff   0    2m\n"
        )
        found = [pod for _, pod in find_unhealthy_pods(namespace="prod")]
        self.assertIn("web-1", found)
        self.assertIn("img-1", found)
        self.assertNotIn("web-2", found)

    def test_completed_pods_are_not_treated_as_failures(self):
        self._stub("job-x   0/1   Completed   0   1h\n")
        self.assertEqual(find_unhealthy_pods(namespace="prod"), [])

    def test_partially_ready_pod_is_flagged(self):
        """1/2 ready with status Running is a real failure the STATUS hides."""
        self._stub("api-1   1/2   Running   0   10m\n")
        found = [pod for _, pod in find_unhealthy_pods(namespace="prod")]
        self.assertEqual(found, ["api-1"])

    def test_all_namespaces_output_keeps_the_namespace(self):
        self._stub("payments   api-1   0/1   CrashLoopBackOff   3   5m\n")
        self.assertEqual(find_unhealthy_pods(all_namespaces=True), [("payments", "api-1")])

    def test_unparseable_line_is_skipped_not_fatal(self):
        self._stub("garbage\n\nweb-1   0/1   CrashLoopBackOff   1   1m\n")
        found = [pod for _, pod in find_unhealthy_pods(namespace="prod")]
        self.assertEqual(found, ["web-1"])


class TestCaptureIsRedacted(unittest.TestCase):
    def test_written_capture_never_contains_the_secret(self):
        """Redaction happens on the way to disk, so no unredacted copy exists."""
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            stats = write_capture(
                out_dir, "describe",
                "kubectl describe pod web-1 -n prod",
                "Environment:\n      DB_PASSWORD:  hunter2\n",
            )
            written = (out_dir / "describe.txt").read_text()
            self.assertNotIn("hunter2", written)
            self.assertIn("REDACTED", written)
            self.assertEqual(stats.get("key-value"), 1)

    def test_capture_records_the_originating_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            write_capture(out_dir, "pods", "kubectl get pods -n prod", "NAME   READY\n")
            written = (out_dir / "pods.txt").read_text()
            self.assertIn("$ kubectl get pods -n prod", written)


if __name__ == "__main__":
    unittest.main()
