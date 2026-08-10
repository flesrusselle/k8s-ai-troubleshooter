#!/usr/bin/env python3
"""
k8s-ai-troubleshooter MCP Server

Serves the repository's diagnostic knowledge to MCP-compatible clients over the
Model Context Protocol's stdio transport: newline-delimited JSON-RPC 2.0 on
stdin/stdout.

Implemented with the standard library only. This project's cost model is $0 and
its dependency list is deliberately short; an MCP server is a small enough
protocol that taking on an SDK to speak it would be the larger cost.

Exposed tools:

- `list_runbooks`         — every runbook, with id, category and path
- `get_runbook`           — full runbook text by id
- `get_decision_tree`     — decision tree YAML by id
- `query_command_safety`  — safety tier and reason for a kubectl/helm command
- `route_symptom`         — map an observed signal to the runbook that handles it

`route_symptom` is the one that changes how a session goes: it lets a client
resolve `CrashLoopBackOff` or exit code 137 to a runbook deterministically,
rather than inferring the right file from a list of names.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

sys.path.insert(0, str(REPO_ROOT / "scripts"))

from safety import classify, classify_command_safety  # noqa: E402

#: Fallback when a client does not name a protocol version. Any version the
#: client does request is echoed back instead, so this server stays usable as
#: the spec revises.
DEFAULT_PROTOCOL_VERSION = "2024-11-05"

SERVER_INFO = {"name": "k8s-ai-troubleshooter", "version": "1.0.0"}

# `classify_command_safety` is re-exported so that callers which imported it
# from this module before the logic moved to scripts/safety.py keep working.
__all__ = [
    "load_runbooks_index", "query_command_safety", "classify_command_safety",
    "get_runbook", "get_decision_tree", "route_symptom", "list_tools", "handle_request", "serve",
]


# ---------------------------------------------------------------------------
# Knowledge access
# ---------------------------------------------------------------------------

def load_runbooks_index():
    runbooks = []
    for file_path in sorted((REPO_ROOT / "runbooks").rglob("*.md")):
        runbooks.append({
            "id": file_path.stem,
            "category": file_path.parent.name,
            "path": str(file_path.relative_to(REPO_ROOT)),
        })
    return runbooks


def get_runbook(runbook_id: str) -> dict:
    """Return a runbook's full text by id (its filename without .md)."""
    for entry in load_runbooks_index():
        if entry["id"] == runbook_id:
            return {
                **entry,
                "content": (REPO_ROOT / entry["path"]).read_text(encoding="utf-8"),
            }
    known = ", ".join(sorted(e["id"] for e in load_runbooks_index()))
    raise ValueError(f"unknown runbook {runbook_id!r}. Known runbooks: {known}")


def get_decision_tree(tree_id: str) -> dict:
    """Return a decision tree's raw YAML by id (its filename without .yaml)."""
    path = REPO_ROOT / "decision-trees" / f"{tree_id}.yaml"
    if not path.exists():
        known = ", ".join(sorted(p.stem for p in (REPO_ROOT / "decision-trees").glob("*.yaml")))
        raise ValueError(f"unknown decision tree {tree_id!r}. Known trees: {known}")
    return {
        "id": tree_id,
        "path": str(path.relative_to(REPO_ROOT)),
        "content": path.read_text(encoding="utf-8"),
    }


def query_command_safety(command_str: str) -> dict:
    """
    Evaluate the safety classification of a kubectl or helm command.

    Classification logic lives in `scripts/safety.py`, which is the single
    implementation shared by this adapter and the test suite, and which is
    verified against `commands/*.yaml` in CI.
    """
    result = classify(command_str)
    return {
        "command": command_str,
        "safety": result.safety,
        "reason": result.reason,
        "automatic_execution_allowed": result.safety in ("SAFE_READ", "SAFE_DIAGNOSTIC"),
    }


#: Below this length, a catalogued signal is too generic to match as a substring
#: of a longer observed string. Without this, the event reason `Failed` — which
#: ImagePullBackOff legitimately lists — matches nearly every error line in the
#: cluster and outranks the runbook that actually applies.
MIN_SUBSTRING_SIGNAL = 8


def _match_score(catalogued: str, observed: str):
    """
    Score how well a catalogued signal matches observed text, or None.

    Specificity wins: an exact match beats a long phrase, which beats a short
    token. `Liveness probe failed` must outrank `Failed` when both appear in the
    same log line, or routing sends the investigation to the wrong runbook.
    """
    if catalogued == observed:
        return 1000
    if len(catalogued) >= MIN_SUBSTRING_SIGNAL and catalogued in observed:
        return len(catalogued)
    if len(observed) >= MIN_SUBSTRING_SIGNAL and observed in catalogued:
        return len(observed)
    return None


def route_symptom(signal: str) -> dict:
    """
    Map an observed signal to the runbook that handles it.

    Matching is case-insensitive and works in both directions, so
    `CrashLoopBackOff`, `crashloopbackoff`, and a whole log line containing
    `Liveness probe failed` all resolve. Routes are returned best-first by
    specificity. Unmatched signals fall back to the index's `default_entry`
    rather than returning nothing, because "start at triage" is always a better
    answer than "no idea".
    """
    import yaml

    index = yaml.safe_load((REPO_ROOT / "symptom-index.yaml").read_text(encoding="utf-8"))
    needle = signal.strip().lower()

    matches = []
    for entry in index["entries"]:
        best = None
        for signal_type, values in entry.get("signals", {}).items():
            for value in values:
                score = _match_score(str(value).lower(), needle)
                if score is not None and (best is None or score > best[0]):
                    best = (score, str(value), signal_type)
        if best:
            score, value, signal_type = best
            matches.append({
                "id": entry["id"],
                "summary": entry["summary"],
                "runbook": entry["runbook"],
                "decision_tree": entry.get("decision_tree"),
                "first_command": entry["first_command"],
                "matched_signal": value,
                "matched_on": signal_type,
                "score": score,
            })

    if matches:
        matches.sort(key=lambda m: m["score"], reverse=True)
        return {"signal": signal, "matched": True, "routes": matches}

    return {
        "signal": signal,
        "matched": False,
        "routes": [{
            "id": "triage",
            "summary": "No signal matched. Establish blast radius first.",
            "runbook": index["default_entry"],
            "decision_tree": None,
            "first_command": "kubectl get pods --all-namespaces --field-selector=status.phase!=Running",
            "matched_signal": None,
            "matched_on": None,
        }],
    }


# ---------------------------------------------------------------------------
# MCP protocol
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "list_runbooks",
        "description": "List every available Kubernetes diagnostic runbook with its id, category and path.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_runbook",
        "description": "Read the full text of a diagnostic runbook by id, e.g. 'crashloopbackoff'.",
        "inputSchema": {
            "type": "object",
            "properties": {"runbook_id": {"type": "string", "description": "Runbook id (filename without .md)."}},
            "required": ["runbook_id"],
        },
    },
    {
        "name": "get_decision_tree",
        "description": "Read a machine-readable decision tree by id, e.g. 'pod-failure'.",
        "inputSchema": {
            "type": "object",
            "properties": {"tree_id": {"type": "string", "description": "Tree id (filename without .yaml)."}},
            "required": ["tree_id"],
        },
    },
    {
        "name": "query_command_safety",
        "description": (
            "Classify a kubectl or helm command into SAFE_READ, SAFE_DIAGNOSTIC, "
            "HUMAN_APPROVAL_REQUIRED or DESTRUCTIVE. Call this before running any command."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"command": {"type": "string", "description": "The full command string."}},
            "required": ["command"],
        },
    },
    {
        "name": "route_symptom",
        "description": (
            "Map an observed signal — a pod status, event reason, exit code or error "
            "string — to the runbook that handles it. Use this instead of guessing."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"signal": {"type": "string", "description": "e.g. 'CrashLoopBackOff', '137', 'FailedMount'."}},
            "required": ["signal"],
        },
    },
]


def list_tools():
    return TOOLS


def _call_tool(name, arguments):
    if name == "list_runbooks":
        return {"runbooks": load_runbooks_index()}
    if name == "get_runbook":
        return get_runbook(arguments["runbook_id"])
    if name == "get_decision_tree":
        return get_decision_tree(arguments["tree_id"])
    if name == "query_command_safety":
        return query_command_safety(arguments["command"])
    if name == "route_symptom":
        return route_symptom(arguments["signal"])
    raise ValueError(f"unknown tool: {name}")


def _result(request_id, payload):
    return {"jsonrpc": "2.0", "id": request_id, "result": payload}


def _error(request_id, code, message):
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle_request(request):
    """
    Handle one JSON-RPC request, returning the response dict or None.

    None means "send nothing", which is correct for notifications: a JSON-RPC
    notification has no id and must not be answered.
    """
    method = request.get("method")
    request_id = request.get("id")
    params = request.get("params") or {}

    if request_id is None and method != "initialize":
        return None  # notification

    if method == "initialize":
        return _result(request_id, {
            "protocolVersion": params.get("protocolVersion", DEFAULT_PROTOCOL_VERSION),
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        })

    if method == "tools/list":
        return _result(request_id, {"tools": list_tools()})

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            payload = _call_tool(name, arguments)
        except KeyError as exc:
            return _result(request_id, {
                "content": [{"type": "text", "text": f"Missing required argument: {exc}"}],
                "isError": True,
            })
        except Exception as exc:
            # Tool failures are reported in-band so the model can react to them,
            # rather than as protocol errors that surface only to the client.
            return _result(request_id, {
                "content": [{"type": "text", "text": str(exc)}],
                "isError": True,
            })
        return _result(request_id, {
            "content": [{"type": "text", "text": json.dumps(payload, indent=2)}],
            "isError": False,
        })

    if method == "ping":
        return _result(request_id, {})

    return _error(request_id, -32601, f"Method not found: {method}")


def serve(stdin=None, stdout=None):
    """Run the stdio transport loop until EOF."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout

    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            stdout.write(json.dumps(_error(None, -32700, "Parse error")) + "\n")
            stdout.flush()
            continue

        response = handle_request(request)
        if response is not None:
            stdout.write(json.dumps(response) + "\n")
            stdout.flush()


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print(json.dumps({
            "status": "ok",
            "runbooks_count": len(load_runbooks_index()),
            "tools": [t["name"] for t in list_tools()],
        }))
        return

    if len(sys.argv) > 2 and sys.argv[1] == "--classify":
        print(json.dumps(query_command_safety(sys.argv[2]), indent=2))
        return

    if len(sys.argv) > 2 and sys.argv[1] == "--route":
        print(json.dumps(route_symptom(sys.argv[2]), indent=2))
        return

    serve()


if __name__ == "__main__":
    main()
