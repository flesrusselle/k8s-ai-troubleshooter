# API Server Unreachable Runbook

## Purpose
Diagnose the case where `kubectl` itself cannot reach or authenticate to the
cluster — the failure that must be excluded before any other investigation is
meaningful.

## When to Use
`kubectl` hangs, times out, or returns a connection or authentication error
rather than data about the cluster.

## Safety Level
`SAFE_READ`

## Symptoms
- `The connection to the server <host> was refused - did you specify the right host or port?`
- `Unable to connect to the server: dial tcp ... i/o timeout`.
- `error: You must be logged in to the server (Unauthorized)`.
- `x509: certificate has expired or is not yet valid`.
- Commands succeed intermittently, or take 30+ seconds.

## Quick Diagnosis

Establish whether the problem is your client, your credentials, or the cluster —
in that order, because each is cheaper to check than the next.

```bash
# 1. Which cluster are you even talking to?
kubectl config current-context
kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}{"\n"}'

# 2. Is the endpoint reachable at the network level?
kubectl cluster-info

# 3. Authentication versus authorization
kubectl auth whoami

# 4. Control plane component health
kubectl get --raw='/readyz?verbose' 2>&1 | head -20
```

## Detailed Investigation

```text
kubectl fails
       ↓
Connection refused / timeout      → network or endpoint problem
Unauthorized                      → credentials expired or wrong
x509 error                        → certificate problem
Forbidden                         → you ARE connected; see rbac-forbidden.md
Slow but working                  → control plane under load
       ↓
Is the context the one you meant?
       ↓ no  → wrong cluster; nothing is broken
       ↓ yes
Does the endpoint respond outside kubectl?
       ↓ no  → endpoint down, DNS wrong, or network path blocked
       ↓ yes → credential or certificate problem
```

1. **Check the context first.** A surprising share of "the cluster is down"
   reports are a `kubectl` pointed at a cluster that was deleted, or at staging
   while looking at production dashboards. It costs one command to exclude.
2. **`Forbidden` means success, not failure.** You reached the API server and it
   authenticated you; it declined the action. That is an RBAC question and
   belongs to a different runbook.
3. **Certificate expiry is the classic silent outage.** Client certificates and
   the API server's serving certificate both expire, typically after a year.
   Nothing changed, no deploy occurred, and the cluster becomes unreachable at a
   precise moment — often for every operator simultaneously.
4. **Token expiry looks like a cluster outage from one machine only.** Cloud
   provider tokens embedded in kubeconfig are short-lived. If colleagues can
   reach the cluster and you cannot, re-authenticate before investigating
   anything cluster-side.
5. **Slow-but-working points at etcd or API server load**, not connectivity.
   `--v=6` reveals where the time goes.
6. **A managed control plane can be reachable while nodes are not.** `kubectl get
   nodes` returning `NotReady` for everything is a node or network problem, not
   an API server problem — the API server answered.

## Decision Tree
Self-contained; branch on the error class as above.

## Evidence to Collect
- Exact error text — refused, timeout, Unauthorized, or x509.
- Current context and the server URL it resolves to.
- Whether other operators can reach the same cluster.
- Expiry dates on the client certificate and any cached token.
- `/readyz?verbose` output, if the endpoint answers at all.
- Whether the failure began at a round-numbered time with no change.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| `connection refused`, endpoint resolves | API server process down, or port blocked | High |
| `i/o timeout` | Network path blocked — firewall, VPN, security group | High |
| `Unauthorized`, colleagues unaffected | Your token or certificate expired | High |
| `x509: certificate has expired` | Cluster or client certificate expired | High |
| Broke at a precise time, no change made | Certificate expiry | High |
| Works, but slowly | etcd or API server under load | Medium |
| `Forbidden` | Connected and authenticated — RBAC, not connectivity | High |
| Wrong resources returned | Wrong context; you are on another cluster | High |

## Confirmation
Confirm reachability independently of credentials:

```bash
kubectl cluster-info dump --output-directory=/tmp/k8s-dump 2>&1 | head -5
kubectl get --raw='/livez' 2>&1
```

`ok` from `/livez` proves the API server is alive and shifts the investigation to
credentials or authorization. A timeout on both confirms the endpoint itself is
unreachable from your network position.

## Remediation
Re-authenticate to refresh an expired token, renew expired certificates, correct
the kubeconfig context or server URL, restore network access such as a VPN, or —
for a genuinely down control plane — follow your provider's recovery procedure.
Node-level control plane recovery is outside this project's read-only scope.

## Human Approval Required
- Re-authentication commands are provider-specific and run by the operator, not by an assistant.
- `kubectl config use-context <context>` — changes which cluster subsequent commands target
- Any control plane restart or certificate renewal on a node — **DESTRUCTIVE**, performed outside this repository's scope

## Related Runbooks
- [cluster-health.md](cluster-health.md)
- [certificate-expiry.md](certificate-expiry.md)
- [../security/rbac-forbidden.md](../security/rbac-forbidden.md)
- [../nodes/node-not-ready.md](../nodes/node-not-ready.md)

## Official Documentation
- [Troubleshooting kubectl](https://kubernetes.io/docs/tasks/debug/debug-cluster/troubleshooting-kubectl/)
- [Cluster Troubleshooting](https://kubernetes.io/docs/tasks/debug/debug-cluster/)
