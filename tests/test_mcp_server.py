import io
import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "integrations" / "mcp"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import server
import session_log
from server import (
    get_decision_tree,
    get_runbook,
    handle_request,
    list_tools,
    load_runbooks_index,
    log_diagnosis,
    query_command_safety,
    route_symptom,
    serve,
)


def call_tool(name, arguments):
    """Invoke a tool through the protocol layer and decode its payload."""
    response = handle_request({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    })
    result = response["result"]
    return json.loads(result["content"][0]["text"]), result["isError"]


class TestProtocol(unittest.TestCase):
    def test_initialize_echoes_the_clients_protocol_version(self):
        """Echoing keeps the server usable as the spec revises."""
        response = handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {}},
        })
        self.assertEqual(response["result"]["protocolVersion"], "2025-06-18")
        self.assertEqual(response["result"]["serverInfo"]["name"], "k8s-ai-troubleshooter")

    def test_initialize_without_a_version_falls_back(self):
        response = handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(response["result"]["protocolVersion"], server.DEFAULT_PROTOCOL_VERSION)

    def test_notifications_get_no_response(self):
        """A JSON-RPC notification has no id and must not be answered."""
        self.assertIsNone(handle_request({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_unknown_method_is_a_protocol_error(self):
        response = handle_request({"jsonrpc": "2.0", "id": 9, "method": "nope"})
        self.assertEqual(response["error"]["code"], -32601)

    def test_ping(self):
        self.assertEqual(handle_request({"jsonrpc": "2.0", "id": 2, "method": "ping"})["result"], {})

    def test_tools_list_advertises_every_tool_with_a_schema(self):
        tools = handle_request({"jsonrpc": "2.0", "id": 3, "method": "tools/list"})["result"]["tools"]
        names = {t["name"] for t in tools}
        self.assertEqual(names, {
            "list_runbooks", "get_runbook", "get_decision_tree",
            "query_command_safety", "route_symptom", "log_diagnosis",
        })
        for tool in tools:
            with self.subTest(tool=tool["name"]):
                self.assertTrue(tool["description"].strip())
                self.assertEqual(tool["inputSchema"]["type"], "object")


class TestStdioTransport(unittest.TestCase):
    def test_serve_reads_and_writes_newline_delimited_json(self):
        stdin = io.StringIO(
            '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}\n'
            '{"jsonrpc":"2.0","method":"notifications/initialized"}\n'
            '{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n'
        )
        stdout = io.StringIO()
        serve(stdin=stdin, stdout=stdout)

        lines = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
        # Two requests, one notification: exactly two responses.
        self.assertEqual(len(lines), 2)
        self.assertEqual([line["id"] for line in lines], [1, 2])

    def test_malformed_json_returns_a_parse_error_and_keeps_serving(self):
        stdin = io.StringIO('not json\n{"jsonrpc":"2.0","id":5,"method":"ping"}\n')
        stdout = io.StringIO()
        serve(stdin=stdin, stdout=stdout)

        lines = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
        self.assertEqual(lines[0]["error"]["code"], -32700)
        self.assertEqual(lines[1]["id"], 5)

    def test_blank_lines_are_ignored(self):
        stdout = io.StringIO()
        serve(stdin=io.StringIO('\n\n{"jsonrpc":"2.0","id":1,"method":"ping"}\n'), stdout=stdout)
        self.assertEqual(len(stdout.getvalue().strip().splitlines()), 1)


class TestKnowledgeTools(unittest.TestCase):
    def test_list_runbooks_matches_what_is_on_disk(self):
        on_disk = len(list((REPO_ROOT / "runbooks").rglob("*.md")))
        self.assertEqual(len(load_runbooks_index()), on_disk)

    def test_get_runbook_returns_content(self):
        payload = get_runbook("crashloopbackoff")
        self.assertIn("CrashLoopBackOff", payload["content"])
        self.assertEqual(payload["category"], "pods")

    def test_get_runbook_lists_valid_ids_when_asked_for_a_bad_one(self):
        """An error the model can act on beats a bare failure."""
        with self.assertRaises(ValueError) as ctx:
            get_runbook("does-not-exist")
        self.assertIn("crashloopbackoff", str(ctx.exception))

    def test_get_decision_tree_returns_yaml(self):
        self.assertIn("pod-failure", get_decision_tree("pod-failure")["content"])

    def test_get_decision_tree_rejects_unknown_id(self):
        with self.assertRaises(ValueError):
            get_decision_tree("nope")

    def test_get_decision_tree_rejects_path_traversal(self):
        with self.assertRaises(ValueError):
            get_decision_tree("../README")

    def test_tool_errors_are_reported_in_band(self):
        """isError in the result, not a JSON-RPC error, so the model sees it."""
        payload, is_error = None, None
        response = handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "get_runbook", "arguments": {"runbook_id": "nope"}},
        })
        self.assertTrue(response["result"]["isError"])
        self.assertIn("unknown runbook", response["result"]["content"][0]["text"])

    def test_missing_argument_is_reported_not_crashed(self):
        response = handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "get_runbook", "arguments": {}},
        })
        self.assertTrue(response["result"]["isError"])


class TestSafetyTool(unittest.TestCase):
    def test_destructive_command_is_not_auto_executable(self):
        result = query_command_safety("kubectl delete namespace prod")
        self.assertEqual(result["safety"], "DESTRUCTIVE")
        self.assertFalse(result["automatic_execution_allowed"])

    def test_read_command_is_auto_executable(self):
        result = query_command_safety("kubectl get pods --namespace prod")
        self.assertEqual(result["safety"], "SAFE_READ")
        self.assertTrue(result["automatic_execution_allowed"])

    def test_reason_is_returned_for_the_model_to_relay(self):
        self.assertTrue(query_command_safety("kubectl delete ns prod")["reason"].strip())


class TestSymptomRouting(unittest.TestCase):
    def test_exact_signal_routes(self):
        result = route_symptom("CrashLoopBackOff")
        self.assertTrue(result["matched"])
        self.assertEqual(result["routes"][0]["runbook"], "runbooks/pods/crashloopbackoff.md")

    def test_routing_is_case_insensitive(self):
        self.assertTrue(route_symptom("crashloopbackoff")["matched"])

    def test_signal_embedded_in_a_log_line_still_routes(self):
        result = route_symptom("Warning  Unhealthy  Liveness probe failed: HTTP probe failed")
        self.assertTrue(result["matched"])
        self.assertIn("probes.md", result["routes"][0]["runbook"])

    def test_exit_code_routes_to_oomkilled(self):
        self.assertEqual(route_symptom("137")["routes"][0]["runbook"], "runbooks/pods/oomkilled.md")

    def test_unmatched_signal_falls_back_to_triage(self):
        """'Start at triage' beats 'no idea'."""
        result = route_symptom("zzzz totally unrecognised zzzz")
        self.assertFalse(result["matched"])
        self.assertEqual(result["routes"][0]["runbook"], "runbooks/triage.md")

    def test_capacity_and_constraint_failures_route_differently(self):
        """
        Both produce FailedScheduling, and they have different fixes: one needs
        capacity, the other needs a toleration or label. Listing the same signal
        under both entries makes the choice a coin toss.
        """
        capacity = route_symptom("0/5 nodes are available: 5 Insufficient memory")
        constraint = route_symptom(
            "0/12 nodes are available: 8 node(s) had untolerated taint"
        )
        self.assertEqual(capacity["routes"][0]["runbook"], "runbooks/pods/pending.md")
        self.assertEqual(
            constraint["routes"][0]["runbook"], "runbooks/scheduling/taints-affinity.md"
        )

    def test_newly_covered_signals_resolve_to_their_own_runbook(self):
        expected = {
            "violates PodSecurity": "runbooks/security/pod-security-admission.md",
            "Cannot evict pod as it would violate the pod's disruption budget":
                "runbooks/scheduling/pdb-eviction.md",
            "Multi-Attach error for volume": "runbooks/storage/multi-attach.md",
            "is forbidden": "runbooks/security/rbac-forbidden.md",
            "x509: certificate has expired": "runbooks/cluster/certificate-expiry.md",
            "Init:CrashLoopBackOff": "runbooks/pods/init-containers.md",
            "exceeded quota": "runbooks/scheduling/resourcequota.md",
            "failed calling webhook": "runbooks/security/admission-webhook.md",
            "BackoffLimitExceeded": "runbooks/workloads/job-failures.md",
        }
        for signal, runbook in expected.items():
            with self.subTest(signal=signal):
                self.assertEqual(route_symptom(signal)["routes"][0]["runbook"], runbook)

    def test_ecosystem_signals_resolve_to_their_own_runbook(self):
        expected = {
            "ComparisonError": "runbooks/ecosystem/argocd-sync-failure.md",
            "sidecar injection": "runbooks/ecosystem/service-mesh-sidecar.md",
            "PeerAuthentication": "runbooks/ecosystem/service-mesh-mtls.md",
            "too many certificates already issued": "runbooks/ecosystem/cert-manager-issuance.md",
        }
        for signal, runbook in expected.items():
            with self.subTest(signal=signal):
                self.assertEqual(route_symptom(signal)["routes"][0]["runbook"], runbook)

    def test_every_route_carries_a_first_command(self):
        for signal in ["CrashLoopBackOff", "FailedMount", "Evicted", "unmatched"]:
            with self.subTest(signal=signal):
                self.assertTrue(route_symptom(signal)["routes"][0]["first_command"])


class TestLogDiagnosisTool(unittest.TestCase):
    """
    log_diagnosis is what makes a session outlive the conversation it happened
    in. Its one real invariant is that confidence values cannot drift — a
    session log where one entry says "High" and another says "Certain" cannot
    be grouped by scripts/session_log.py's --summary, which defeats the reason
    it exists.
    """

    def setUp(self):
        import os
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self._log_file = Path(self._tmp.name) / "sessions.jsonl"
        self._original_env = os.environ.get("K8S_AI_TROUBLESHOOTER_SESSION_LOG")
        os.environ["K8S_AI_TROUBLESHOOTER_SESSION_LOG"] = str(self._log_file)

    def tearDown(self):
        import os

        if self._original_env is None:
            os.environ.pop("K8S_AI_TROUBLESHOOTER_SESSION_LOG", None)
        else:
            os.environ["K8S_AI_TROUBLESHOOTER_SESSION_LOG"] = self._original_env
        self._tmp.cleanup()

    def test_valid_confidence_is_logged(self):
        result = log_diagnosis("CrashLoopBackOff", "runbooks/pods/crashloopbackoff.md", "High")
        self.assertTrue(result["logged"])
        entries = session_log.read_entries(self._log_file)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["confidence"], "High")

    def test_invalid_confidence_is_rejected_and_nothing_is_written(self):
        with self.assertRaises(ValueError):
            log_diagnosis("x", "y", "Certain")
        self.assertEqual(session_log.read_entries(self._log_file), [])

    def test_optional_fields_are_recorded_when_given(self):
        log_diagnosis(
            "OOMKilled", "runbooks/pods/oomkilled.md", "High",
            root_cause="memory limit too low", evidence_bundle="/tmp/bundle",
            notes="raised limit to 512Mi",
        )
        entry = session_log.read_entries(self._log_file)[0]
        self.assertEqual(entry["root_cause"], "memory limit too low")
        self.assertEqual(entry["evidence_bundle"], "/tmp/bundle")

    def test_tool_is_reachable_through_the_protocol_layer(self):
        payload, is_error = call_tool("log_diagnosis", {
            "signal": "CrashLoopBackOff",
            "runbook": "runbooks/pods/crashloopbackoff.md",
            "confidence": "Medium",
        })
        self.assertFalse(is_error)
        self.assertTrue(payload["logged"])

    def test_invalid_confidence_through_the_protocol_layer_is_reported_in_band(self):
        """A rejected tool call must surface to the model, not crash the server."""
        response = handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "log_diagnosis",
                       "arguments": {"signal": "x", "runbook": "y", "confidence": "super sure"}},
        })
        self.assertTrue(response["result"]["isError"])
        self.assertIn("confidence must be one of", response["result"]["content"][0]["text"])

    def test_tool_is_advertised_with_an_enum_constrained_confidence(self):
        tool = next(t for t in list_tools() if t["name"] == "log_diagnosis")
        self.assertEqual(
            set(tool["inputSchema"]["properties"]["confidence"]["enum"]),
            {"High", "Medium", "Low"},
        )


if __name__ == "__main__":
    unittest.main()
