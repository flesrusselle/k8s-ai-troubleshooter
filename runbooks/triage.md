# Cluster Triage — Start Here

## Purpose
Establish the blast radius of a problem before investigating it, then route to
the runbook that handles the specific failure. This is the entry point when the
report is vague — "the app is down", "something is broken in prod" — and no
single pod has been named yet.

## When to Use
Use this first, always, unless you already know the exact failure mode. Opening
`crashloopbackoff.md` because one pod is crashing wastes the investigation when
forty pods are crashing on one node and the node is the actual fault.

## Safety Level
`SAFE_READ`

## Symptoms
- A user reports an outage without naming a workload.
- Multiple unrelated services are failing at once.
- A deploy "did not work" with no further detail.
- Alerts firing across more than one namespace.

## Quick Diagnosis

Establish scope before depth. These four commands answer "how big is this?" and
take under a minute:

```bash
# 1. Is the control plane answering at all?
kubectl cluster-info

# 2. Are the nodes healthy? A node fault explains many pod faults at once.
kubectl get nodes -o wide

# 3. What is failing, cluster-wide?
kubectl get pods --all-namespaces --field-selector=status.phase!=Running

# 4. What has the cluster been complaining about recently?
kubectl get events --all-namespaces --sort-by=.lastTimestamp | tail -40
```

To capture all of this at once, redacted and ready to hand to an assistant:

```bash
python3 scripts/collect.py --all-namespaces --output evidence-bundle
```

## Detailed Investigation

Work outside-in. Each level explains failures at the level below it, so
diagnosing in this order stops you from investigating a symptom whose cause is
one layer up:

```text
Control plane reachable?
       ↓ no  → runbooks/cluster/cluster-health.md
       ↓ yes
All nodes Ready?
       ↓ no  → runbooks/nodes/node-not-ready.md
       ↓ yes, but under pressure → runbooks/nodes/node-pressure.md
       ↓ yes
Failures spread across many namespaces?
       ↓ yes → suspect shared infrastructure:
               DNS      → runbooks/networking/coredns.md
               storage  → runbooks/storage/pvc-pending.md
               admission/quota → runbooks/cluster/cluster-health.md
       ↓ no
Failures confined to one workload?
       ↓ yes → match the pod state against symptom-index.yaml
```

**Step 1 — Scope it.** Count distinct namespaces and nodes in the failure set.
One namespace and one node means a workload problem. Many namespaces on one node
means a node problem. Many namespaces on many nodes means shared infrastructure
or control plane.

**Step 2 — Order by time.** The oldest anomalous event is usually the cause; the
rest are consequences. `--sort-by=.lastTimestamp` exists for this.

**Step 3 — Route on the literal signal.** Take the exact `STATUS` string, event
`REASON`, or error text and match it against `symptom-index.yaml`. Do not
paraphrase the signal before matching it — `ErrImagePull` and `ImagePullBackOff`
are different points in the same failure and the index distinguishes them.

**Step 4 — Confirm before concluding.** Every runbook has a Confirmation
section. A hypothesis that has not been checked against evidence is a guess, and
guesses cost more than the command that would have settled them.

## Decision Tree
`decision-trees/pod-failure.yaml` once the failure is workload-scoped;
`decision-trees/node-health.yaml` when nodes are implicated.

## Evidence to Collect
- Count of failing pods, grouped by namespace and by node.
- `Ready` / `NotReady` state and conditions for every node.
- The 40 most recent cluster events, oldest anomaly first.
- Time the first failure was observed, versus the time of the last deploy.
- Whether the failure set shares an image, a node, a volume, or a secret.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| Failures across many namespaces, all on one node | Node fault — disk, kubelet, network | High |
| Failures across many namespaces and many nodes | Shared infrastructure: DNS, storage backend, admission webhook, registry | High |
| Failures confined to one namespace after a deploy | Bad configuration or image in that release | High |
| `kubectl` itself hangs or times out | Control plane or API server unreachable | High |
| Every new pod is `Pending` cluster-wide | Exhausted capacity, or a failing admission webhook rejecting creates | Medium |
| Failures started at a round-numbered time with no deploy | Certificate expiry, token rotation, or a scheduled job | Medium |

## Confirmation
Confirm scope by grouping the failing set:

```bash
# Failures grouped by node — a single node dominating is the diagnosis
kubectl get pods --all-namespaces --field-selector=status.phase!=Running \
  -o custom-columns='NS:.metadata.namespace,POD:.metadata.name,NODE:.spec.nodeName'
```

If one node owns most of the failures, stop and go to the node runbooks. If the
failures are spread evenly, the cause is shared infrastructure, not any pod.

## Remediation
Triage performs no remediation. It selects the runbook that does. Follow the
routed runbook's own Remediation section, which carries the approval gate
appropriate to that fix.

## Blast Radius
Triage itself has none — every command is read-only. The blast radius of the
*routed* remediation is stated in the runbook that owns it, and must be read
before acting on it.

## Human Approval Required
None — every command in this runbook is read-only. Any remediation reached
through routing inherits the approval requirements of its own runbook, and those
still apply.

## Verification
Triage succeeded when you can state, in one sentence, whether the fault is
workload-scoped, node-scoped, or cluster-scoped, and name the runbook you are
opening next. If you cannot, you have not finished scoping — do not proceed to
depth.

## Rollback
Nothing to roll back. If routing led to the wrong runbook, return here and
re-scope rather than continuing down a path that does not fit the evidence.

## Related Runbooks
- [find-failing-pods.md](pods/find-failing-pods.md)
- [cluster-health.md](cluster/cluster-health.md)
- [node-not-ready.md](nodes/node-not-ready.md)
- [node-pressure.md](nodes/node-pressure.md)

## Official Documentation
- [Troubleshooting Clusters](https://kubernetes.io/docs/tasks/debug/debug-cluster/)
- [Troubleshooting Applications](https://kubernetes.io/docs/tasks/debug/debug-application/)
