# PodDisruptionBudget & Eviction Runbook

## Purpose
Diagnose drains, node upgrades and autoscaler scale-downs blocked by a
PodDisruptionBudget, and PDBs that fail to protect a workload they should.

## When to Use
`kubectl drain` hangs or repeats `Cannot evict pod as it would violate the pod's
disruption budget`, or a cluster upgrade stalls on one node indefinitely.

## Safety Level
`SAFE_READ`

## Symptoms
- `error when evicting pods/"x": Cannot evict pod as it would violate the pod's disruption budget`.
- A node has been `SchedulingDisabled` for hours with pods still on it.
- Cluster autoscaler logs "cannot scale down, pdb blocking".
- A managed node group upgrade times out.

## Quick Diagnosis

```bash
# 1. ALLOWED DISRUPTIONS is the field that decides everything
kubectl get pdb -A

# 2. Which PDB covers the pod that will not evict
kubectl describe pdb <name> -n <namespace>

# 3. Are the covered pods actually healthy?
kubectl get pods -n <namespace> -l <pdb-selector> -o wide

# 4. What is still on the node
kubectl get pods -A --field-selector=spec.nodeName=<node> -o wide
```

## Detailed Investigation

```text
Eviction blocked
       ↓
ALLOWED DISRUPTIONS = 0?
       ↓ yes
Are all covered pods healthy?
       ↓ no  → the PDB is correctly refusing; fix the unhealthy pods first
       ↓ yes
Does replica count leave any headroom over minAvailable?
       ↓ no  → PDB is mathematically unsatisfiable: replicas == minAvailable
       ↓ yes → transient; retry after pods settle
```

1. **A PDB blocking a drain is usually correct.** It is doing exactly its job:
   refusing to take availability below the floor you declared. The question is
   whether the floor is right, not how to bypass it.
2. **`minAvailable` equal to the replica count is a deadlock.** A Deployment with
   3 replicas and `minAvailable: 3` can never have a pod evicted voluntarily. The
   node can never be drained. This is the single most common misconfiguration
   here, and it is silent until the first upgrade.
3. **Unhealthy pods count against you.** `ALLOWED DISRUPTIONS` is computed from
   *healthy* pods. If one of three replicas is already crash-looping, a
   `minAvailable: 2` budget yields zero allowed disruptions — the drain blocks
   because of an unrelated failure elsewhere in the workload.
4. **PDBs govern voluntary disruption only.** A node that crashes, or a kubelet
   that evicts under memory pressure, ignores the budget entirely. A PDB is not
   a guarantee of availability; it is a constraint on planned operations.
5. **A single-replica workload with any PDB is undrainable** unless
   `maxUnavailable: 1` is used instead of `minAvailable: 1`.

## Decision Tree
`decision-trees/node-health.yaml` when the blocked eviction is part of node
maintenance.

## Evidence to Collect
- `ALLOWED DISRUPTIONS`, `MIN AVAILABLE` / `MAX UNAVAILABLE`, `CURRENT HEALTHY`,
  `DESIRED HEALTHY` from the PDB.
- Actual replica count of the covered workload.
- Health of every pod the PDB selects — including ones on other nodes.
- Whether the workload has a controller that can reschedule it at all.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| `ALLOWED DISRUPTIONS: 0`, replicas == `minAvailable` | Unsatisfiable budget; drain impossible by construction | High |
| `ALLOWED DISRUPTIONS: 0`, one pod unhealthy | Unrelated failure consuming the budget | High |
| Single replica with `minAvailable: 1` | Undrainable; use `maxUnavailable: 1` | High |
| Drain blocked on a bare pod | Pod has no controller, so it cannot be recreated | High |
| Autoscaler never scales down a node | PDB on a workload with no headroom | High |
| PDB exists but pod evicted anyway | Involuntary disruption — PDBs do not apply | High |
| PDB selects nothing | Selector does not match any pod labels | Medium |

## Confirmation
Confirm the arithmetic directly:

```bash
kubectl get pdb <name> -n <namespace> \
  -o custom-columns='NAME:.metadata.name,MIN:.spec.minAvailable,HEALTHY:.status.currentHealthy,DESIRED:.status.desiredHealthy,ALLOWED:.status.disruptionsAllowed'
```

`currentHealthy == desiredHealthy` with `disruptionsAllowed: 0` confirms the
budget has no headroom. Whether that is a misconfiguration or an unhealthy pod
is answered by comparing `currentHealthy` against the replica count.

## Remediation
Restore the unhealthy pods so the budget regains headroom; or scale the workload
up temporarily to create room for the drain; or correct a budget that was
written as `minAvailable: <replica count>`. Deleting the PDB removes the
protection cluster-wide for that workload and should be a last resort during an
incident, with restoration tracked.

## Blast Radius
Deleting or loosening a PDB removes availability protection for that workload
cluster-wide, including during unrelated future maintenance. `--disable-eviction`
bypasses every PDB on the node at once and can take a service to zero replicas.

## Human Approval Required
- `kubectl scale deployment/<name> --replicas=<n+1> -n <namespace>`
- `kubectl patch pdb <name> -n <ns> --type=merge -p '{"spec":{"minAvailable":<n>}}'`
- `kubectl drain <node> --delete-emptydir-data --ignore-daemonsets` — **DESTRUCTIVE**, evicts every pod on the node
- `kubectl drain <node> --disable-eviction` — **DESTRUCTIVE**, bypasses PDBs entirely
- `kubectl delete pdb <name> -n <namespace>` — **DESTRUCTIVE**, removes availability protection

## Verification
```bash
kubectl get pdb <name> -n <namespace>
kubectl get pods -n <namespace> -l <selector> -o wide
```
Verified when `ALLOWED DISRUPTIONS` is at least 1 and the drain proceeds. Confirm
the workload still has its intended replica count afterwards — a drain that
succeeded by taking a service below its floor is not a success.

## Rollback
Restore the original `minAvailable`/`maxUnavailable`, or recreate a deleted
PDB. Pods evicted during the window are not returned; they were rescheduled
elsewhere if capacity allowed, and are simply gone if it did not.

## Related Runbooks
- [../nodes/node-not-ready.md](../nodes/node-not-ready.md)
- [../nodes/node-pressure.md](../nodes/node-pressure.md)
- [../pods/evicted.md](../pods/evicted.md)
- [taints-affinity.md](taints-affinity.md)

## Official Documentation
- [Disruptions](https://kubernetes.io/docs/concepts/workloads/pods/disruptions/)
- [Specifying a Disruption Budget](https://kubernetes.io/docs/tasks/run-application/configure-pdb/)
- [Safely Drain a Node](https://kubernetes.io/docs/tasks/administer-cluster/safely-drain-node/)
