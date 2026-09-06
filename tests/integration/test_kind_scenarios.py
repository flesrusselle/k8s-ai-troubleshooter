"""
Integration tests against a real Kubernetes API server.

Every other test in this project mocks `kubectl` or feeds hand-written JSON to
the code under test. That proves the matching logic is correct against strings
we chose ourselves — it does not prove those strings are what Kubernetes
actually emits. These tests induce a real failure (a crashing pod, a tainted
node, a permanently-unbound PVC), read back the literal signal the API server
produced, and assert `route_symptom` — the same function an assistant calls —
resolves it to the runbook a human would expect.

Safety: these tests taint real nodes and create/delete namespaces. They refuse
to run against anything whose current-context does not literally start with
"kind-", checked both before the module's tests are collected (via
`unittest.skipUnless`, so a plain `python -m unittest discover tests` run
without a kind cluster configured just reports them skipped) and again in
`setUpClass` as defense in depth. Use scripts/integration/run_kind_tests.sh,
which creates and destroys its own disposable cluster, rather than pointing
this at a cluster you use for anything else.
"""

import json
import shutil
import subprocess
import sys
import time
import unittest
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "integrations" / "mcp"))

from collect import find_unhealthy_pods  # noqa: E402
from server import route_symptom  # noqa: E402


def _kubectl(*args, check=True, input_text=None, timeout=30):
    result = subprocess.run(
        ["kubectl", *args], capture_output=True, text=True,
        input=input_text, timeout=timeout,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"kubectl {' '.join(args)} failed:\n{result.stderr}")
    return result


def _current_context():
    result = subprocess.run(
        ["kubectl", "config", "current-context"], capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _kind_cluster_available():
    if not shutil.which("kubectl"):
        return False
    if not _current_context().startswith("kind-"):
        return False
    try:
        return _kubectl("cluster-info", check=False, timeout=10).returncode == 0
    except (subprocess.TimeoutExpired, RuntimeError):
        return False


REQUIRES_KIND = unittest.skipUnless(
    _kind_cluster_available(),
    "requires kubectl configured against a 'kind-*' context — "
    "run scripts/integration/run_kind_tests.sh",
)


@REQUIRES_KIND
class TestKindScenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        context = _current_context()
        if not context.startswith("kind-"):
            raise RuntimeError(
                f"refusing to run kind integration tests against non-kind context {context!r}"
            )
        cls.namespace = f"k8s-ai-troubleshooter-it-{uuid.uuid4().hex[:8]}"
        _kubectl("create", "namespace", cls.namespace)

    @classmethod
    def tearDownClass(cls):
        _kubectl("delete", "namespace", cls.namespace, "--wait=false", check=False)

    def _apply(self, manifest):
        _kubectl("apply", "-f", "-", input_text=manifest)

    def _wait_for_pod_json(self, name, predicate, timeout=180):
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            result = _kubectl("get", "pod", name, "--namespace", self.namespace, "--output", "json", check=False)
            if result.returncode == 0:
                last = json.loads(result.stdout)
                if predicate(last):
                    return last
            time.sleep(2)
        status = json.dumps((last or {}).get("status", {}), indent=2)
        events = _kubectl("get", "events", "--namespace", self.namespace, check=False).stdout
        self.fail(
            f"pod {name} never reached expected state within {timeout}s;\n"
            f"status:\n{status}\n"
            f"events:\n{events}"
        )

    def _wait_for_event(self, object_name, reason, timeout=45):
        deadline = time.time() + timeout
        while time.time() < deadline:
            result = _kubectl(
                "get", "events", "--namespace", self.namespace,
                "--field-selector", f"involvedObject.name={object_name},reason={reason}",
                "-o", "json", check=False,
            )
            if result.returncode == 0:
                events = json.loads(result.stdout).get("items", [])
                if events:
                    return events[-1]["message"]
            time.sleep(2)
        self.fail(f"no {reason!r} event appeared for {object_name!r} within {timeout}s")

    @staticmethod
    def _container_waiting_reason(pod):
        for cs in pod.get("status", {}).get("containerStatuses") or []:
            reason = (cs.get("state", {}).get("waiting") or {}).get("reason")
            if reason:
                return reason
        return None

    # -----------------------------------------------------------------------

    def test_crashloopbackoff_is_detected_and_routes_correctly(self):
        name = "crash-test"
        self._apply(f"""
apiVersion: v1
kind: Pod
metadata:
  name: {name}
  namespace: {self.namespace}
spec:
  restartPolicy: Always
  containers:
    - name: crasher
      image: busybox:1.36
      command: ["sh", "-c", "exit 1"]
""")
        pod = self._wait_for_pod_json(
            name, lambda p: self._container_waiting_reason(p) == "CrashLoopBackOff"
        )
        signal = self._container_waiting_reason(pod)

        route = route_symptom(signal)
        self.assertTrue(route["matched"])
        self.assertEqual(route["routes"][0]["runbook"], "runbooks/pods/crashloopbackoff.md")

        # The same collector an assistant would run must also flag this pod —
        # against a live namespace, not a hand-built JSON fixture.
        unhealthy = find_unhealthy_pods(namespace=self.namespace)
        self.assertIn((self.namespace, name), unhealthy)

    def test_imagepullbackoff_is_detected_and_routes_correctly(self):
        name = "badimage-test"
        self._apply(f"""
apiVersion: v1
kind: Pod
metadata:
  name: {name}
  namespace: {self.namespace}
spec:
  containers:
    - name: badimage
      image: k8s-ai-troubleshooter-test/definitely-does-not-exist:v0
""")
        pod = self._wait_for_pod_json(
            name,
            lambda p: self._container_waiting_reason(p) in ("ImagePullBackOff", "ErrImagePull"),
            timeout=60,
        )
        signal = self._container_waiting_reason(pod)

        route = route_symptom(signal)
        self.assertTrue(route["matched"])
        self.assertEqual(route["routes"][0]["runbook"], "runbooks/pods/imagepullbackoff.md")

        unhealthy = find_unhealthy_pods(namespace=self.namespace)
        self.assertIn((self.namespace, name), unhealthy)

    def test_pvc_referencing_unknown_storageclass_routes_correctly(self):
        pvc_name, pod_name = "pvc-test", "pvc-pod-test"
        self._apply(f"""
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: {pvc_name}
  namespace: {self.namespace}
spec:
  accessModes: ["ReadWriteOnce"]
  storageClassName: definitely-does-not-exist
  resources:
    requests:
      storage: 1Gi
---
apiVersion: v1
kind: Pod
metadata:
  name: {pod_name}
  namespace: {self.namespace}
spec:
  containers:
    - name: idle
      image: busybox:1.36
      command: ["sleep", "3600"]
      volumeMounts:
        - name: data
          mountPath: /data
  volumes:
    - name: data
      persistentVolumeClaim:
        claimName: {pvc_name}
""")
        # A PVC referencing a nonexistent StorageClass has no provisioner to
        # fail, so it never gets a ProvisioningFailed event — it just sits
        # unbound. The reliable, version-stable signal is the scheduler's own
        # refusal to place a pod that mounts an unbound PVC.
        message = self._wait_for_event(pod_name, "FailedScheduling", timeout=45)

        pvc = json.loads(_kubectl("get", "pvc", pvc_name, "--namespace", self.namespace, "--output", "json").stdout)
        self.assertEqual(pvc["status"]["phase"], "Pending")

        route = route_symptom(message)
        self.assertTrue(route["matched"])
        self.assertEqual(route["routes"][0]["runbook"], "runbooks/storage/pvc-pending.md")

    def test_untolerated_taint_blocks_scheduling_and_routes_correctly(self):
        node = _kubectl("get", "nodes", "-o", "jsonpath={.items[0].metadata.name}").stdout.strip()
        taint = "k8s-ai-troubleshooter-test=blocked:NoSchedule"
        _kubectl("taint", "node", node, taint, "--overwrite")
        try:
            name = "taint-test"
            self._apply(f"""
apiVersion: v1
kind: Pod
metadata:
  name: {name}
  namespace: {self.namespace}
spec:
  containers:
    - name: idle
      image: busybox:1.36
      command: ["sleep", "3600"]
""")
            message = self._wait_for_event(name, "FailedScheduling", timeout=30)
            self.assertIn("untolerated taint", message)

            route = route_symptom(message)
            self.assertTrue(route["matched"])
            self.assertEqual(route["routes"][0]["runbook"], "runbooks/scheduling/taints-affinity.md")
        finally:
            _kubectl("taint", "node", node, f"{taint}-", check=False)


if __name__ == "__main__":
    unittest.main()
