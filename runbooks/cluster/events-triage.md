# Cluster Events Triage Runbook

## Purpose
Extract a timeline from Kubernetes events, so the first cause is separated from
the cascade of consequences that follows it.

## When to Use
Multiple things are failing and their relationship is unclear, or an incident
needs a timeline reconstructed after the fact.

## Safety Level
`SAFE_READ`

## Symptoms
- Many alerts firing across namespaces within a short window.
- Failures that appear unrelated but started together.
- A need to answer "what happened first?".

## Quick Diagnosis

Default event output is ordered arbitrarily, which makes cause and effect
indistinguishable. Always sort.

```bash
# 1. Cluster-wide, oldest first — the top of this list is where to look
kubectl get events --all-namespaces --sort-by=.metadata.creationTimestamp

# 2. Warnings only
kubectl get events --all-namespaces --field-selector type=Warning \
  --sort-by=.lastTimestamp

# 3. Count by reason — reveals the dominant failure mode
kubectl get events --all-namespaces -o json \
  | python3 -c "
import sys, json, collections
items = json.load(sys.stdin)['items']
counts = collections.Counter(i['reason'] for i in items)
for reason, n in counts.most_common(15): print(f'{n:5}  {reason}')
"

# 4. Events for one object
kubectl get events -n <namespace> --field-selector involvedObject.name=<name>
```

## Detailed Investigation

```text
Many failures
       ↓
Sort events oldest-first
       ↓
Find the first Warning that is not a consequence of another
       ↓
Group the rest by reason and by node
       ↓
One node dominates?        → node fault, see node runbooks
One reason dominates?      → route that reason via symptom-index.yaml
Spread evenly?             → shared infrastructure or control plane
```

1. **Events expire, typically after one hour.** They are a live signal, not an
   audit log. If an incident is older than that, the events are gone and you must
   work from metrics, logs, or `kubectl get -o yaml` state instead. Collect them
   early — this is a strong argument for running the evidence collector at the
   start of an incident rather than the end.
2. **Sort by `lastTimestamp` for recency, by `creationTimestamp` for onset.**
   A repeating event keeps updating `lastTimestamp` and its `COUNT`, so sorting
   by it hides when the problem actually began.
3. **`COUNT` distinguishes a spike from a grind.** One `FailedScheduling` with
   count 400 is a single pod retrying, not 400 broken pods.
4. **Read the causal chain in the right direction.** `FailedMount` follows
   `ProvisioningFailed`; `Unhealthy` precedes `Killing` precedes `BackOff`.
   Investigating the last event in a chain wastes the investigation.
5. **Normal events are not noise.** `Scheduled`, `Pulled`, `Created`, `Started`
   establish the timeline that makes the warnings interpretable — particularly
   the gap between `Created` and `Started`.

## Decision Tree
Route the dominant event reason through `symptom-index.yaml`.

## Evidence to Collect
- Cluster-wide events sorted oldest-first, captured before they expire.
- Counts grouped by `reason` and by `involvedObject.kind`.
- The node distribution of warning events.
- The earliest warning that is not explained by an earlier one.
- Time of the first event relative to any deploy or infrastructure change.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| Warnings concentrated on one node | Node fault — start at the node runbooks | High |
| `FailedScheduling` dominant cluster-wide | Capacity exhausted, or an admission webhook rejecting creates | High |
| `Unhealthy` then `Killing` then `BackOff` | Probe failure driving restarts — start at probes | High |
| `ProvisioningFailed` then `FailedMount` | Storage backend problem; mount errors are downstream | High |
| `Evicted` across many namespaces | Node resource pressure | High |
| One `FailedScheduling` with a huge COUNT | A single stuck pod retrying, not a cluster-wide fault | High |
| No events at all during a known outage | Events expired, or the control plane was unreachable | Medium |

## Confirmation
Confirm the node-fault hypothesis by grouping warnings by node:

```bash
kubectl get events --all-namespaces --field-selector type=Warning -o json \
  | python3 -c "
import sys, json, collections
items = json.load(sys.stdin)['items']
counts = collections.Counter(
    i.get('source', {}).get('host', 'unknown') for i in items
)
for host, n in counts.most_common(): print(f'{n:5}  {host}')
"
```

One host dominating confirms a node-scoped fault and redirects the investigation
away from the individual workloads.

## Remediation
Events triage produces a routing decision, not a fix. Follow the runbook the
dominant reason routes to, and apply that runbook's remediation with its own
approval gate.

## Human Approval Required
None — every command here is read-only. Remediation reached through routing
inherits the approval requirements of its own runbook.

## Related Runbooks
- [../triage.md](../triage.md)
- [cluster-health.md](cluster-health.md)
- [../nodes/node-pressure.md](../nodes/node-pressure.md)
- [../pods/find-failing-pods.md](../pods/find-failing-pods.md)

## Official Documentation
- [Events](https://kubernetes.io/docs/reference/kubernetes-api/cluster-resources/event-v1/)
- [Debug Running Pods](https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/)
