# DaemonSet Not Scheduling Runbook

## Purpose
Diagnose DaemonSets that do not place a pod on every node they should, leaving
gaps in cluster-wide agents such as CNI, logging, monitoring and storage drivers.

## When to Use
`DESIRED` is lower than the node count, or `READY` is lower than `DESIRED`, and
specific nodes have no pod from the DaemonSet.

## Safety Level
`SAFE_READ`

## Symptoms
- `kubectl get daemonset` shows `DESIRED 5` on a 7-node cluster.
- Logs or metrics missing from exactly one node.
- A new node joins and never receives the agent.
- Control-plane nodes have no pod while workers do.

## Quick Diagnosis

```bash
# 1. Desired vs current vs ready — the gap tells you which problem you have
kubectl get daemonset <name> --namespace <namespace> -o wide

# 2. Which nodes are missing a pod
kubectl get pods --namespace <namespace> -l <selector> -o wide --sort-by=.spec.nodeName
kubectl get nodes

# 3. Taints on the nodes that were skipped
kubectl get nodes -o custom-columns='NAME:.metadata.name,TAINTS:.spec.taints'

# 4. Why the scheduler declined
kubectl describe daemonset <name> --namespace <namespace>
```

## Detailed Investigation

```text
DaemonSet gap
       ↓
Is DESIRED lower than the node count?
       ↓ yes → the controller decided not to place a pod:
       │        node taint without a matching toleration,
       │        or nodeSelector / affinity excludes the node
       ↓ no (DESIRED correct, READY low)
       → pods exist but are failing: read them as ordinary pod failures
```

1. **`DESIRED` too low is a placement decision, not a failure.** The DaemonSet
   controller evaluates taints, `nodeSelector` and affinity, and simply does not
   create a pod where it does not fit. There is no failing pod to inspect, which
   is why this looks like nothing is wrong.
2. **Control-plane nodes are tainted by default.**
   `node-role.kubernetes.io/control-plane:NoSchedule` means an agent that must
   run everywhere — a CNI or node exporter — needs an explicit toleration.
3. **DaemonSet pods tolerate some conditions automatically.** The controller adds
   tolerations for `not-ready`, `unreachable`, `disk-pressure`,
   `memory-pressure`, `pid-pressure` and `unschedulable`, so DaemonSet pods keep
   running on a node that is rejecting everything else. Custom taints are **not**
   covered.
4. **`nodeSelector` is an easy silent exclusion.** A selector on
   `kubernetes.io/os: linux` quietly skips Windows nodes; one on a custom label
   skips every node that has not been labelled yet, including new ones.
5. **Resource requests still apply.** A DaemonSet pod that does not fit within a
   node's allocatable resources stays `Pending` on that node forever, because
   unlike a Deployment it cannot be placed anywhere else.

## Decision Tree
`decision-trees/node-health.yaml` when specific nodes are implicated.

## Evidence to Collect
- `DESIRED`, `CURRENT`, `READY`, `AVAILABLE` from the DaemonSet.
- Full node list with taints and labels.
- The DaemonSet's `tolerations`, `nodeSelector` and `affinity`.
- Its resource requests versus the skipped node's allocatable capacity.
- Events on any pod that exists but is Pending.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| No pod on control-plane nodes | Missing toleration for the control-plane taint | High |
| One node skipped, others fine | Custom taint on that node without a toleration | High |
| New nodes never get a pod | `nodeSelector` requires a label the node lacks | High |
| Pod Pending on one node only | Requests exceed that node's allocatable resources | High |
| DESIRED correct but READY low | Pods are running and failing — ordinary pod debugging | High |
| Gap appeared after an upgrade | Taint keys changed between versions | Medium |

## Confirmation
Confirm a taint hypothesis by comparing the node's taints against the
DaemonSet's tolerations:

```bash
kubectl get node <node> -o jsonpath='{.spec.taints}{"\n"}'
kubectl get daemonset <name> --namespace <namespace> -o jsonpath='{.spec.template.spec.tolerations}{"\n"}'
```

A taint with no matching toleration is a complete explanation for a missing pod
on that node.

## Remediation
Add the missing toleration, relax or correct the `nodeSelector`, label the nodes
that should be covered, or lower resource requests to fit. For agents that must
run everywhere, a blanket `operator: Exists` toleration is legitimate — but it
also means the pod will run on nodes that are deliberately cordoned, so use it
only for genuinely cluster-wide agents.

## Blast Radius
A DaemonSet change rolls across every node it targets. Adding a broad
toleration places the agent on nodes that were deliberately isolated, including
cordoned ones. Removing a taint affects scheduling for every workload, not just
this DaemonSet.

## Human Approval Required
- `kubectl apply -f <daemonset>.yaml`
- `kubectl label node <node> <key>=<value>`
- `kubectl taint node <node> <key>-` — removing a taint affects every workload's scheduling

## Verification
```bash
kubectl get daemonset <name> --namespace <namespace> -o wide
kubectl get pods --namespace <namespace> -l <selector> -o wide
```
Verified when `DESIRED` equals the number of nodes that should run the agent and
`READY` equals `DESIRED`. `DESIRED` matching alone means the controller intends
to place pods, not that they are running.

## Rollback
`kubectl rollout undo daemonset/<name> --namespace <namespace>` restores the previous
template. A removed taint must be reapplied explicitly, and pods scheduled onto
the node while it was absent will not leave on their own.

## Related Runbooks
- [../scheduling/taints-affinity.md](../scheduling/taints-affinity.md)
- [../pods/pending.md](../pods/pending.md)
- [../nodes/node-not-ready.md](../nodes/node-not-ready.md)
- [../nodes/node-pressure.md](../nodes/node-pressure.md)

## Official Documentation
- [DaemonSet](https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/)
- [Taints and Tolerations](https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/)
