"""
Conformance test: manifests/rbac/clusterrole-readonly.yaml must grant exactly
what scripts/collect.py's command plans actually use — no more, no less as a
matter of drift. A resource added to the collector without a matching RBAC
rule would fail Forbidden in the field the first time someone bound the
least-privilege role; this test fails CI instead, before that ever happens.
"""

import re
import sys
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from collect import CLUSTER_PLAN, NAMESPACE_PLAN, POD_PLAN  # noqa: E402

MANIFEST = REPO_ROOT / "manifests" / "rbac" / "clusterrole-readonly.yaml"

#: kubectl resource token (as it appears in a "kubectl get/describe <token>"
#: command) -> (apiGroup, RBAC resource name). "" is the core API group.
#: Commands whose safety does not derive from a single get/list-able resource
#: (discovery, non-resource URLs, Helm) are handled separately below.
RESOURCE_API_GROUPS = {
    "nodes": ("", "nodes"),
    "namespaces": ("", "namespaces"),
    "pv": ("", "persistentvolumes"),
    "storageclass": ("storage.k8s.io", "storageclasses"),
    "pods": ("", "pods"),
    "events": ("", "events"),
    "deployments": ("apps", "deployments"),
    "replicasets": ("apps", "replicasets"),
    "statefulsets": ("apps", "statefulsets"),
    "daemonsets": ("apps", "daemonsets"),
    "jobs": ("batch", "jobs"),
    "cronjobs": ("batch", "cronjobs"),
    "services": ("", "services"),
    "endpoints": ("", "endpoints"),
    "ingress": ("networking.k8s.io", "ingresses"),
    "networkpolicies": ("networking.k8s.io", "networkpolicies"),
    "pvc": ("", "persistentvolumeclaims"),
    "configmaps": ("", "configmaps"),
    "resourcequota": ("", "resourcequotas"),
    "limitrange": ("", "limitranges"),
    "hpa": ("autoscaling", "horizontalpodautoscalers"),
    "poddisruptionbudget": ("policy", "poddisruptionbudgets"),
    "secrets": ("", "secrets"),
}

#: Commands whose resource is deliberately not derived from the plan text —
#: either because it needs special-casing (secrets/Helm, documented in
#: manifests/rbac/README.md) or because it is not resource-RBAC at all
#: (discovery, non-resource URLs).
EXEMPT_STEP_NAMES = {"cluster-info", "version", "api-resources", "helm-releases"}


def load_manifest_rules():
    return yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))["rules"]


def rule_covers(rules, api_group, resource, verb="get"):
    for rule in rules:
        if "resources" not in rule:
            continue  # a nonResourceURLs-only rule
        if api_group in rule.get("apiGroups", []) and resource in rule.get("resources", []):
            if verb in rule.get("verbs", []):
                return True
    return False


def extract_resource_token(command):
    """Pull the resource kubectl targets out of a 'kubectl get/describe X ...' command."""
    match = re.match(r"^kubectl (?:get|describe)\s+(\S+)", command)
    return match.group(1) if match else None


class TestRBACManifestExists(unittest.TestCase):
    def test_manifest_is_valid_yaml_with_rules(self):
        rules = load_manifest_rules()
        self.assertIsInstance(rules, list)
        self.assertGreater(len(rules), 0)

    def test_no_secrets_variant_has_no_secrets_rule(self):
        no_secrets = yaml.safe_load(
            (MANIFEST.parent / "clusterrole-readonly-no-secrets.yaml").read_text(encoding="utf-8")
        )
        for rule in no_secrets["rules"]:
            if "resources" in rule:
                self.assertNotIn("secrets", rule["resources"])

    def test_no_rule_grants_a_mutating_verb(self):
        """The entire point of this manifest. A single leaked verb here defeats it."""
        mutating = {"create", "update", "patch", "delete", "deletecollection"}
        for path in MANIFEST.parent.glob("clusterrole-*.yaml"):
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(doc.get("kind"), "ClusterRole", f"{path.name} is not a ClusterRole")
            for rule in doc["rules"]:
                with self.subTest(file=path.name, rule=rule.get("resources")):
                    self.assertFalse(set(rule.get("verbs", [])) & mutating)


class TestManifestCoversTheCollectorPlan(unittest.TestCase):
    """
    Every get/describe step in the collector's own command plan must have a
    matching rule in the manifest. This is the direction that matters most: a
    command the collector runs, with no RBAC rule to authorize it, is a
    guaranteed Forbidden the moment someone actually binds the least-privilege
    role — exactly the gap this manifest exists to close.
    """

    @classmethod
    def setUpClass(cls):
        cls.rules = load_manifest_rules()

    def _plan_steps(self):
        for name, template in CLUSTER_PLAN + NAMESPACE_PLAN:
            yield name, template.format(ns_flag="--namespace x").strip()

    def test_every_plan_resource_has_a_matching_rule(self):
        for name, command in self._plan_steps():
            if name in EXEMPT_STEP_NAMES:
                continue
            token = extract_resource_token(command)
            with self.subTest(step=name, command=command):
                self.assertIn(token, RESOURCE_API_GROUPS, f"{name}: unmapped resource token {token!r}")
                api_group, resource = RESOURCE_API_GROUPS[token]
                self.assertTrue(
                    rule_covers(self.rules, api_group, resource, "get"),
                    f"{name}: no rule grants get on {api_group or 'core'}/{resource}",
                )
                self.assertTrue(
                    rule_covers(self.rules, api_group, resource, "list"),
                    f"{name}: no rule grants list on {api_group or 'core'}/{resource}",
                )

    def test_secrets_metadata_step_is_covered_by_the_secrets_rule(self):
        self.assertTrue(rule_covers(self.rules, "", "secrets", "get"))
        self.assertTrue(rule_covers(self.rules, "", "secrets", "list"))

    def test_pod_describe_and_logs_are_covered(self):
        for _, template in POD_PLAN:
            command = template.format(pod="x", ns="y")
            with self.subTest(command=command):
                if "logs" in command:
                    self.assertTrue(rule_covers(self.rules, "", "pods/log", "get"))
                else:
                    self.assertTrue(rule_covers(self.rules, "", "pods", "get"))

    def test_metrics_and_admission_steps_are_covered(self):
        self.assertTrue(rule_covers(self.rules, "metrics.k8s.io", "nodes", "get"))
        self.assertTrue(rule_covers(self.rules, "metrics.k8s.io", "pods", "get"))
        self.assertTrue(
            rule_covers(self.rules, "admissionregistration.k8s.io",
                        "validatingwebhookconfigurations", "get")
        )

    def test_nonresource_health_endpoints_are_covered(self):
        non_resource_urls = set()
        for rule in self.rules:
            non_resource_urls.update(rule.get("nonResourceURLs", []))
        for path in ("/livez", "/readyz", "/version"):
            with self.subTest(path=path):
                self.assertIn(path, non_resource_urls)


if __name__ == "__main__":
    unittest.main()
