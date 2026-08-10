#!/usr/bin/env bash
# Spin up a throwaway kind cluster, run the integration test suite against it,
# and tear it down — whether the tests pass or fail.
#
# These tests induce real failures (CrashLoopBackOff, a tainted node, a
# permanently-unbound PVC) against a live API server, then check that
# route_symptom resolves the real signal to the runbook a human would expect.
# See tests/integration/test_kind_scenarios.py for the safety guard: they
# refuse to run against any context that doesn't start with "kind-". This
# script never touches an existing cluster — it always creates and deletes
# its own, named separately from any cluster you may already have.
set -euo pipefail

CLUSTER_NAME="k8s-ai-troubleshooter-test"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if ! command -v kind >/dev/null 2>&1; then
  echo "kind is not installed." >&2
  echo "See https://kind.sigs.k8s.io/docs/user/quick-start/#installation" >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
  echo "Docker is not running. kind requires a running Docker (or Podman) daemon." >&2
  exit 1
fi

cleanup() {
  echo "--- deleting kind cluster '${CLUSTER_NAME}' ---"
  kind delete cluster --name "${CLUSTER_NAME}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# Delete any leftover cluster from a previous interrupted run before starting.
kind delete cluster --name "${CLUSTER_NAME}" >/dev/null 2>&1 || true

echo "--- creating kind cluster '${CLUSTER_NAME}' ---"
kind create cluster --name "${CLUSTER_NAME}" --wait 120s

echo "--- running integration tests ---"
cd "${REPO_ROOT}"
python3 -m unittest discover -s tests/integration -p 'test_*.py' -v
