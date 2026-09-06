# Scheduling Constraints Runbook

## Purpose
Diagnose pods that cannot be scheduled because of taints, node affinity, pod
affinity or anti-affinity, or topology spread constraints — as distinct from
pods that cannot be scheduled because the cluster is out of resources.

## When to Use
`FailedScheduling` events that mention taints, affinity, selectors or topology
rather than `Insufficient cpu` or `Insufficient memory`.

## Safety Level
`SAFE_READ`

## Symptoms
- `0/12 nodes are available: 8 node(s) had untolerated taint {...}, 4 node(s) didn't match Pod's node affinity/selector`.
- Pods schedule in one cluster and not another with identical capacity.
- A Deployment scales to 4 but the 5th replica is permanently `Pending`.
- Pods cluster onto one node despite anti-affinity.

## Quick Diagnosis

The `FailedScheduling` message is a per-reason census of every node. Read it as
arithmetic: the counts must sum to the total node count.

```bash
# 1. The message names every reason and how many nodes each excluded
kubectl describe pod <pod-name> --namespace <namespace> | grep -A15 Events

# 2. Node taints and labels
kubectl get nodes -o custom-columns='NAME:.metadata.name,TAINTS:.spec.taints'
kubectl get nodes --show-labels

# 3. What the pod is asking for
kubectl get pod <pod-name> --namespace <namespace> \
  -o jsonpath='{.spec.tolerations}{"\n"}{.spec.affinity}{"\n"}{.spec.topologySpreadConstraints}{"\n"}'
```

## Detailed Investigation

```text
0/N nodes are available: <reasons>
       ↓
Split the message by reason and check the arithmetic
       ↓
"untolerated taint"        → node repels the pod; add a toleration
"didn't match node affinity/selector" → pod demands a label the node lacks
"didn't match pod affinity" → required companion pod not present
"didn't satisfy anti-affinity" → a conflicting pod already occupies the domain
"didn't match topology spread" → placement would exceed maxSkew
"Insufficient cpu/memory"  → capacity problem — see pending.md instead
```

1. **Taints repel; affinity attracts.** A taint is a property of the node saying
   "nothing runs here unless it tolerates me". Affinity is a property of the pod
   saying "I only run where this is true". Both produce `Pending`, and the fix is
   on the opposite object in each case.
2. **`requiredDuringScheduling` is absolute.** `preferred` degrades gracefully;
   `required` will leave a pod Pending forever. Most unexpected permanent
   Pending traces to a `required` rule written when the cluster had a topology it
   no longer has.
3. **Anti-affinity has a replica ceiling.** `requiredDuringScheduling`
   anti-affinity with `topologyKey: kubernetes.io/hostname` means at most one
   replica per node. Scaling beyond the node count is then impossible by
   construction — the 5th replica of a 4-node cluster can never be placed.
4. **Topology spread depends on labelled nodes.** If nodes lack
   `topology.kubernetes.io/zone`, spread constraints over that key cannot be
   satisfied. `whenUnsatisfiable: DoNotSchedule` then blocks; `ScheduleAnyway`
   only degrades the distribution.
5. **`NoSchedule` and `NoExecute` differ in the past tense.** `NoSchedule`
   affects new placements; `NoExecute` also evicts pods already running. A taint
   added with `NoExecute` will empty a node.

## Decision Tree
`decision-trees/node-health.yaml` when node taints or conditions are implicated.

## Evidence to Collect
- The complete `FailedScheduling` message with its per-reason node counts.
- All node taints, and the pod's tolerations.
- Node labels referenced by `nodeSelector` or `nodeAffinity`.
- `topologySpreadConstraints` and whether nodes carry the topology key.
- Replica count versus the number of eligible nodes, for anti-affinity.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| `had untolerated taint {node-role.kubernetes.io/control-plane}` | Pod tried to land on a control-plane node | High |
| `didn't match Pod's node affinity/selector` | `nodeSelector` names a label no node carries | High |
| Exactly one replica unschedulable, others fine | Hostname anti-affinity; replicas exceed node count | High |
| `didn't match pod topology spread constraints` | `maxSkew` too tight, or nodes missing the topology label | High |
| Pods evicted from a node without a drain | A `NoExecute` taint was added | High |
| Works in staging, fails in prod | Prod nodes lack a label staging has | High |
| `had volume node affinity conflict` | Pod pinned to the zone of its existing volume | High |

## Confirmation
Confirm by checking whether any node satisfies the constraint at all:

```bash
# Does any node carry the required label?
kubectl get nodes -l <key>=<value>
```

An empty result confirms a `nodeSelector` or `requiredDuringScheduling` rule
that no node can satisfy, which is a permanent condition rather than a transient
capacity shortage.

## Remediation
Add the missing toleration, label the nodes the workload expects, relax
`required` rules to `preferred`, reduce replicas to fit an anti-affinity ceiling,
or set `whenUnsatisfiable: ScheduleAnyway` where even distribution is a
preference rather than a requirement.

## Blast Radius
Node labels and taints affect scheduling for every workload, not just the one
being debugged. A `NoExecute` taint evicts running pods immediately. Relaxing a
`required` affinity rule may place a workload somewhere it was deliberately kept
away from — a compliance boundary, a licensed node, a GPU pool.

## Human Approval Required
- `kubectl apply -f <manifest-with-tolerations>.yaml`
- `kubectl label node <node> <key>=<value>`
- `kubectl taint node <node> <key>=<value>:NoExecute` — **evicts running pods immediately**

## Verification
```bash
kubectl get pod <pod-name> --namespace <namespace> -o wide
```
Verified when the pod has a `NODE` assignment and the node is the kind you
intended. Scheduled is not the same as correctly placed: check the node's labels
before treating placement as success.

## Rollback
Reapply the removed taint or restore the original affinity rules. Pods
scheduled while a constraint was relaxed stay where they are until rescheduled —
relaxing a rule then restoring it does not move them back.

## Related Runbooks
- [../pods/pending.md](../pods/pending.md)
- [../workloads/daemonset-not-scheduling.md](../workloads/daemonset-not-scheduling.md)
- [pdb-eviction.md](pdb-eviction.md)
- [../nodes/node-not-ready.md](../nodes/node-not-ready.md)

## Official Documentation
- [Assigning Pods to Nodes](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/)
- [Taints and Tolerations](https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/)
- [Pod Topology Spread Constraints](https://kubernetes.io/docs/concepts/scheduling-eviction/topology-spread-constraints/)
