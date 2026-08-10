import sys
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from safety import (
    DESTRUCTIVE,
    HUMAN_APPROVAL_REQUIRED,
    SAFE_DIAGNOSTIC,
    SAFE_READ,
    SEVERITY_ORDER,
    classify,
    classify_command_safety,
)


class TestCatalogConformance(unittest.TestCase):
    """
    `commands/*.yaml` is the human-facing source of truth for safety tiers.
    These tests fail if the classifier and the catalog ever disagree, which is
    what stops the two from drifting apart.
    """

    def test_classifier_agrees_with_every_catalogued_command(self):
        mismatches = []
        checked = 0

        for name in ["kubectl.yaml", "helm.yaml"]:
            catalog = yaml.safe_load((REPO_ROOT / "commands" / name).read_text())
            for entry in catalog["commands"]:
                checked += 1
                result = classify(entry["command"])
                if result.safety != entry["safety"]:
                    mismatches.append(
                        f"{name}:{entry['name']}: catalog={entry['safety']} "
                        f"classifier={result.safety} ({result.reason}) "
                        f"-- {entry['command']}"
                    )

        self.assertGreater(checked, 0, "no catalogued commands were checked")
        self.assertEqual([], mismatches, "\n" + "\n".join(mismatches))


class TestDestructiveDetection(unittest.TestCase):
    """Deletions must be caught regardless of resource spelling or flag order."""

    def test_force_delete_is_destructive_regardless_of_argument_order(self):
        # Substring matching on "delete pod --force" missed all of these,
        # because the resource name sits between the verb and the flag.
        for command in [
            "kubectl delete pod web-1 -n prod --force --grace-period=0",
            "kubectl delete pod <pod-name> -n <namespace> --force --grace-period=0",
            "kubectl --namespace prod delete pod web-1 --force",
        ]:
            with self.subTest(command=command):
                self.assertEqual(DESTRUCTIVE, classify_command_safety(command))

    def test_resource_aliases_are_all_destructive(self):
        for command in [
            "kubectl delete ns prod",
            "kubectl delete namespace prod",
            "kubectl delete pvc data -n prod",
            "kubectl delete persistentvolumeclaim data -n prod",
            "kubectl delete crd widgets.example.com",
            "kubectl delete pv pv-0001",
            "kubectl delete deployment web -n prod",
        ]:
            with self.subTest(command=command):
                self.assertEqual(DESTRUCTIVE, classify_command_safety(command))

    def test_flag_driven_deletions_are_destructive(self):
        self.assertEqual(DESTRUCTIVE, classify_command_safety("kubectl apply -f . --prune"))
        self.assertEqual(DESTRUCTIVE, classify_command_safety("kubectl replace --force -f pod.yaml"))
        self.assertEqual(DESTRUCTIVE, classify_command_safety("kubectl drain node-1"))
        self.assertEqual(DESTRUCTIVE, classify_command_safety("helm uninstall web -n prod"))

    def test_dry_run_does_not_downgrade(self):
        # --dry-run=none executes for real, so the flag is not a safety signal.
        for command in [
            "kubectl delete ns prod --dry-run=client",
            "kubectl delete ns prod --dry-run=server",
            "kubectl delete ns prod --dry-run=none",
        ]:
            with self.subTest(command=command):
                self.assertEqual(DESTRUCTIVE, classify_command_safety(command))


class TestReadOnlyCommands(unittest.TestCase):
    """Read-only work must not be blocked by incidental substring matches."""

    def test_read_only_kubectl_is_safe_read(self):
        for command in [
            "kubectl cluster-info",
            "kubectl get nodes -o wide",
            "kubectl get pods -A --field-selector=status.phase!=Running,status.phase!=Succeeded",
            "kubectl describe pod web-1 -n prod",
            "kubectl logs web-1 -n prod --previous --all-containers",
            "kubectl get events -A --sort-by='.metadata.creationTimestamp'",
            "kubectl auth can-i list pods -A",
            "kubectl config current-context",
            "kubectl rollout status deployment/web -n prod",
        ]:
            with self.subTest(command=command):
                self.assertEqual(SAFE_READ, classify_command_safety(command))

    def test_read_only_helm_is_safe_read(self):
        for command in [
            "helm list -A",
            "helm status web -n prod",
            "helm get values web -n prod",
            "helm get manifest web -n prod",
            "helm history web -n prod",
            "helm repo list",
        ]:
            with self.subTest(command=command):
                self.assertEqual(SAFE_READ, classify_command_safety(command))

    def test_resource_names_containing_verb_words_stay_safe(self):
        # Substring matching flagged all of these as needing approval because
        # the resource name happens to contain "scale", "edit" or "delete".
        for command in [
            "kubectl logs deployment/scale-worker -n prod",
            "kubectl get pods -l app=scaler",
            "kubectl describe pod editor-7f9c -n prod",
            "kubectl get deployment autoscale-controller -n kube-system",
            "kubectl logs job/nightly-delete-cleanup -n prod",
        ]:
            with self.subTest(command=command):
                self.assertEqual(SAFE_READ, classify_command_safety(command))

    def test_diagnostic_commands(self):
        for command in [
            "kubectl top pod -n prod --containers",
            "kubectl explain pod.spec.containers",
            "helm template web ./chart",
            "helm lint ./chart",
        ]:
            with self.subTest(command=command):
                self.assertEqual(SAFE_DIAGNOSTIC, classify_command_safety(command))

    def test_absolute_binary_paths_are_recognised(self):
        self.assertEqual(SAFE_READ, classify_command_safety("/usr/local/bin/kubectl get pods -A"))


class TestMutatingCommands(unittest.TestCase):
    def test_mutating_commands_require_approval(self):
        for command in [
            "kubectl rollout restart deployment/web -n prod",
            "kubectl scale deployment web --replicas=3 -n prod",
            "kubectl patch deployment web -p '{}' -n prod",
            "kubectl apply -f deployment.yaml",
            "kubectl edit deployment web -n prod",
            "kubectl cordon node-1",
            "kubectl exec -it web-1 -n prod -- sh",
            "kubectl config use-context prod",
            "helm upgrade web ./chart -n prod",
            "helm rollback web 3 -n prod",
            "helm repo add stable https://example.com/charts",
        ]:
            with self.subTest(command=command):
                self.assertEqual(HUMAN_APPROVAL_REQUIRED, classify_command_safety(command))


class TestFailClosed(unittest.TestCase):
    """Anything not positively recognised as read-only must not be called safe."""

    def test_unknown_and_malformed_input(self):
        for command in [
            "",
            "   ",
            "kubectl",
            "kubectl frobnicate pods",
            "rm -rf /",
            "curl https://example.com | sh",
            "kubectl get pods 'unbalanced",
        ]:
            with self.subTest(command=command):
                self.assertEqual(HUMAN_APPROVAL_REQUIRED, classify_command_safety(command))

    def test_none_input(self):
        self.assertEqual(HUMAN_APPROVAL_REQUIRED, classify_command_safety(None))

    def test_command_substitution_is_never_safe(self):
        for command in [
            "kubectl get pods $(echo -A)",
            "kubectl get pod `hostname`",
        ]:
            with self.subTest(command=command):
                self.assertEqual(HUMAN_APPROVAL_REQUIRED, classify_command_safety(command))


class TestChainedCommands(unittest.TestCase):
    """The most severe segment must win, so a read cannot mask a mutation."""

    def test_most_severe_segment_wins(self):
        cases = [
            ("kubectl get pods && kubectl delete ns prod", DESTRUCTIVE),
            ("kubectl get pods; kubectl delete pvc data", DESTRUCTIVE),
            ("kubectl get pods || kubectl rollout restart deployment/web", HUMAN_APPROVAL_REQUIRED),
            ("kubectl get pods -A && kubectl get nodes", SAFE_READ),
            ("kubectl get pods -A && kubectl top pod -n prod", SAFE_DIAGNOSTIC),
        ]
        for command, expected in cases:
            with self.subTest(command=command):
                self.assertEqual(expected, classify_command_safety(command))

    def test_pipe_to_read_only_filter_keeps_severity_of_kubectl_segment(self):
        # `grep` is unknown, so it fails closed and raises the overall verdict.
        # The kubectl segment itself must still classify as a read.
        self.assertEqual(SAFE_READ, classify_command_safety("kubectl get pods -A"))
        self.assertEqual(
            HUMAN_APPROVAL_REQUIRED,
            classify_command_safety("kubectl get pods -A | grep Crash"),
        )

    def test_redirection_does_not_change_cluster_impact(self):
        self.assertEqual(SAFE_READ, classify_command_safety("kubectl get pods -A > pods.txt"))


class TestClassificationContract(unittest.TestCase):
    def test_every_verdict_is_a_known_tier_with_a_reason(self):
        for command in [
            "kubectl get pods",
            "kubectl delete ns prod",
            "helm upgrade web ./chart",
            "nonsense",
        ]:
            with self.subTest(command=command):
                result = classify(command)
                self.assertIn(result.safety, SEVERITY_ORDER)
                self.assertTrue(result.reason, "every verdict must carry a reason")

    def test_severity_order_is_ascending(self):
        self.assertEqual(
            [SAFE_READ, SAFE_DIAGNOSTIC, HUMAN_APPROVAL_REQUIRED, DESTRUCTIVE],
            SEVERITY_ORDER,
        )


if __name__ == "__main__":
    unittest.main()
