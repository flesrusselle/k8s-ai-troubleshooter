import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import collect
import session_log
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
            assert_safe("kubectl rollout restart deployment/api --namespace prod")

    def test_assert_safe_refuses_a_chained_command_hiding_a_delete(self):
        with self.assertRaises(UnsafeCommand):
            assert_safe("kubectl get pods && kubectl delete ns prod")

    def test_run_command_refuses_before_executing(self):
        """The guard must sit in front of the subprocess, not after it."""
        with self.assertRaises(UnsafeCommand):
            collect.run_command("kubectl delete pod web-1 --namespace prod --force")


class TestPlanScoping(unittest.TestCase):
    def test_namespace_is_threaded_into_namespaced_commands(self):
        commands = [c for _, c in build_plan(namespace="payments")]
        self.assertTrue(any("get pods --namespace payments" in c for c in commands))

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

    def _stub_pods(self, pods):
        payload = json.dumps({"items": pods})
        collect.run_command = lambda command, timeout=60: (True, payload)

    def _stub_raw(self, output, ok=True):
        collect.run_command = lambda command, timeout=60: (ok, output)

    @staticmethod
    def _pod(name, namespace="prod", phase="Running", ready=True,
             waiting_reason=None, terminated_reason=None, terminated_exit=0,
             status_reason=None, deletion_timestamp=None):
        """Build a minimal pod JSON item — only the fields _pod_is_unhealthy reads."""
        state = {}
        if waiting_reason:
            state["waiting"] = {"reason": waiting_reason}
        if terminated_reason:
            state["terminated"] = {"reason": terminated_reason, "exitCode": terminated_exit}
        container_status = {"ready": ready}
        if state:
            container_status["state"] = state

        metadata = {"name": name, "namespace": namespace}
        if deletion_timestamp:
            metadata["deletionTimestamp"] = deletion_timestamp

        status = {"phase": phase, "containerStatuses": [container_status]}
        if status_reason:
            status["reason"] = status_reason

        return {"metadata": metadata, "status": status}

    def test_crashloopbackoff_is_flagged(self):
        self._stub_pods([
            self._pod("web-1", ready=False, waiting_reason="CrashLoopBackOff"),
            self._pod("web-2", ready=True),
        ])
        found = [pod for _, pod in find_unhealthy_pods(namespace="prod")]
        self.assertEqual(found, ["web-1"])

    def test_imagepullbackoff_is_flagged(self):
        self._stub_pods([self._pod("img-1", ready=False, waiting_reason="ImagePullBackOff")])
        found = [pod for _, pod in find_unhealthy_pods(namespace="prod")]
        self.assertEqual(found, ["img-1"])

    def test_oomkilled_is_flagged(self):
        self._stub_pods([
            self._pod("web-1", ready=False, terminated_reason="OOMKilled", terminated_exit=137),
        ])
        found = [pod for _, pod in find_unhealthy_pods(namespace="prod")]
        self.assertEqual(found, ["web-1"])

    def test_succeeded_job_pod_is_not_a_failure(self):
        """A Job pod that ran to completion is healthy, whatever its READY count."""
        self._stub_pods([self._pod("job-x", phase="Succeeded", ready=False)])
        self.assertEqual(find_unhealthy_pods(namespace="prod"), [])

    def test_pending_phase_is_flagged(self):
        self._stub_pods([self._pod("pending-1", phase="Pending", ready=False)])
        found = [pod for _, pod in find_unhealthy_pods(namespace="prod")]
        self.assertEqual(found, ["pending-1"])

    def test_failed_phase_is_flagged(self):
        self._stub_pods([self._pod("evicted-1", phase="Failed", status_reason="Evicted", ready=False)])
        found = [pod for _, pod in find_unhealthy_pods(namespace="prod")]
        self.assertEqual(found, ["evicted-1"])

    def test_terminating_pod_is_flagged(self):
        self._stub_pods([
            self._pod("stuck-1", ready=True, deletion_timestamp="2026-08-10T00:00:00Z"),
        ])
        found = [pod for _, pod in find_unhealthy_pods(namespace="prod")]
        self.assertEqual(found, ["stuck-1"])

    def test_partially_ready_running_pod_is_flagged(self):
        """Running with one of several containers not ready is a real failure
        the STATUS column alone hides."""
        pod = self._pod("api-1", phase="Running", ready=True)
        pod["status"]["containerStatuses"].append({"ready": False})
        self._stub_pods([pod])
        found = [pod for _, pod in find_unhealthy_pods(namespace="prod")]
        self.assertEqual(found, ["api-1"])

    def test_fully_ready_running_pod_is_healthy(self):
        self._stub_pods([self._pod("web-2", phase="Running", ready=True)])
        self.assertEqual(find_unhealthy_pods(namespace="prod"), [])

    def test_all_namespaces_keeps_the_pods_own_namespace(self):
        self._stub_pods([
            self._pod("api-1", namespace="payments", ready=False, waiting_reason="CrashLoopBackOff"),
        ])
        self.assertEqual(find_unhealthy_pods(all_namespaces=True), [("payments", "api-1")])

    def test_unparseable_output_is_skipped_not_fatal(self):
        self._stub_raw("not json at all")
        self.assertEqual(find_unhealthy_pods(namespace="prod"), [])

    def test_command_failure_returns_empty_rather_than_raising(self):
        self._stub_raw("Forbidden", ok=False)
        self.assertEqual(find_unhealthy_pods(namespace="prod"), [])


class TestCaptureIsRedacted(unittest.TestCase):
    def test_written_capture_never_contains_the_secret(self):
        """Redaction happens on the way to disk, so no unredacted copy exists."""
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            stats = write_capture(
                out_dir, "describe",
                "kubectl describe pod web-1 --namespace prod",
                "Environment:\n      DB_PASSWORD:  hunter2\n",
            )
            written = (out_dir / "describe.txt").read_text()
            self.assertNotIn("hunter2", written)
            self.assertIn("REDACTED", written)
            self.assertEqual(stats.get("key-value"), 1)

    def test_capture_records_the_originating_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            write_capture(out_dir, "pods", "kubectl get pods --namespace prod", "NAME   READY\n")
            written = (out_dir / "pods.txt").read_text()
            self.assertIn("$ kubectl get pods --namespace prod", written)


class TestCollectWritesToSessionLog(unittest.TestCase):
    """
    A recurring incident is invisible unless every run leaves a trace. This is
    the other side of that: proving `collect()` itself writes one, not just
    that scripts/session_log.py works in isolation.
    """

    def setUp(self):
        import os

        self._tmp_log = tempfile.TemporaryDirectory()
        self._tmp_out = tempfile.TemporaryDirectory()
        self._log_file = Path(self._tmp_log.name) / "sessions.jsonl"
        self._original_env = os.environ.get("K8S_AI_TROUBLESHOOTER_SESSION_LOG")
        os.environ["K8S_AI_TROUBLESHOOTER_SESSION_LOG"] = str(self._log_file)
        self._original_run_command = collect.run_command
        collect.run_command = lambda command, timeout=60: (True, '{"items": []}')

    def tearDown(self):
        import os

        collect.run_command = self._original_run_command
        if self._original_env is None:
            os.environ.pop("K8S_AI_TROUBLESHOOTER_SESSION_LOG", None)
        else:
            os.environ["K8S_AI_TROUBLESHOOTER_SESSION_LOG"] = self._original_env
        self._tmp_log.cleanup()
        self._tmp_out.cleanup()

    def test_a_run_appends_exactly_one_entry(self):
        out_dir = Path(self._tmp_out.name) / "bundle"
        collect.collect(out_dir, namespace="prod", include_optional=False, include_pods=False, log=lambda *a: None)
        entries = session_log.read_entries(self._log_file)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["source"], "collect")
        self.assertEqual(entries[0]["scope"], "prod")

    def test_evidence_bundle_path_is_recorded(self):
        out_dir = Path(self._tmp_out.name) / "bundle"
        collect.collect(out_dir, namespace="prod", include_optional=False, include_pods=False, log=lambda *a: None)
        entry = session_log.read_entries(self._log_file)[0]
        self.assertEqual(entry["evidence_bundle"], str(out_dir.resolve()))

    def test_all_namespaces_scope_is_recorded_distinctly(self):
        out_dir = Path(self._tmp_out.name) / "bundle"
        collect.collect(out_dir, all_namespaces=True, include_optional=False, include_pods=False, log=lambda *a: None)
        entry = session_log.read_entries(self._log_file)[0]
        self.assertEqual(entry["scope"], "all-namespaces")

    def test_disabling_pod_collection_omits_the_unhealthy_count_rather_than_lying(self):
        out_dir = Path(self._tmp_out.name) / "bundle"
        collect.collect(out_dir, namespace="prod", include_optional=False, include_pods=False, log=lambda *a: None)
        entry = session_log.read_entries(self._log_file)[0]
        self.assertNotIn("unhealthy_pod_count", entry)


if __name__ == "__main__":
    unittest.main()
