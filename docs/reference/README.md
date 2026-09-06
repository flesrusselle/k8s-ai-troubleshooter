# Reference Tables

Lookup tables for the raw signals Kubernetes emits. Each entry maps a literal
value to what it means and which runbook handles it.

| Reference | Covers |
| :--- | :--- |
| [exit-codes.md](exit-codes.md) | Container exit codes, and why 137 is not always OOM |
| [pod-states.md](pod-states.md) | Phases, waiting reasons, terminated reasons, and the composite `STATUS` strings kubectl invents |
| [event-reasons.md](event-reasons.md) | Event `REASON` values grouped by the component that emits them |

For programmatic routing use [`symptom-index.yaml`](../../symptom-index.yaml),
which maps the same signals to runbooks in machine-readable form, or the
`route_symptom` tool in the [MCP server](../usage/mcp.md).

---

## The three facts worth memorising

**1. `Running` does not mean healthy.** A pod can be `Running` with `0/1` ready
and serve no traffic. The `READY` column carries more information than `STATUS`,
and a phase filter will not find these pods.

**2. Exit code 137 is SIGKILL, not "out of memory".** It could be the OOM
killer, a failed liveness probe, or an expired grace period. Check
`lastState.terminated.reason` before raising a memory limit.

**3. `FailedCreate` events live on the ReplicaSet.** When admission rejects a
pod — quota, Pod Security, a webhook — the Deployment is accepted and the
ReplicaSet is refused. `kubectl get pods` shows nothing and
`describe deployment` looks healthy. Look at
`kubectl describe replicaset --namespace <namespace>`.
