# StatefulSet Stuck Runbook

## Purpose
Diagnose StatefulSets that will not progress: an ordinal stuck forever, a
rollout that halts partway, or replicas that never scale up.

## When to Use
A StatefulSet shows fewer ready replicas than desired and stays that way, or a
rolling update stops at one pod and does not continue.

## Safety Level
`SAFE_READ`

## Symptoms
- `kubectl get statefulset` shows `2/5` and does not advance.
- Pod `<name>-2` is `Pending` or `CrashLoopBackOff` while `-0` and `-1` are fine.
- An update reached one pod and stopped.
- Deleting the stuck pod recreates it in the same broken state.

## Quick Diagnosis

```bash
# 1. StatefulSet state and update strategy
kubectl describe statefulset <name> -n <namespace>

# 2. Which ordinal is stuck — order matters here
kubectl get pods -n <namespace> -l app=<label> --sort-by=.metadata.name

# 3. The per-ordinal PVC, which is the usual culprit
kubectl get pvc -n <namespace> -l app=<label>

# 4. The blocked pod itself
kubectl describe pod <name>-<ordinal> -n <namespace>
```

## Detailed Investigation

```text
StatefulSet not progressing
       ↓
Which ordinal is blocked?
       ↓
Its PVC bound?
       ↓ no  → storage problem; every later ordinal is blocked behind it
       ↓ yes
Pod scheduled?
       ↓ no  → volume node affinity may pin it to an unavailable node
       ↓ yes
Pod ready?
       ↓ no  → readiness probe failing; ordered rollout will never continue
       ↓ yes
Check updateStrategy — partition may be holding the rollout deliberately
```

1. **Ordering is the defining behaviour.** With the default
   `podManagementPolicy: OrderedReady`, pod *N* is not created until pod *N-1*
   is Running **and Ready**. One unready pod halts everything after it
   permanently. This is by design, and it is why a StatefulSet "stops" rather
   than degrading.
2. **A failing readiness probe is therefore fatal to the rollout**, not merely
   to traffic. This differs sharply from a Deployment, which continues.
3. **PVCs are created per ordinal and never deleted** by scaling down. Scaling
   3 → 1 → 3 reuses the original volumes, so a pod can come back with corrupt or
   stale data that has nothing to do with the current image.
4. **`volumeClaimTemplates` are immutable.** Changing storage size or class in
   the template is rejected; the StatefulSet must be recreated (with
   `--cascade=orphan` to preserve pods) or the PVCs resized individually.
5. **`updateStrategy.rollingUpdate.partition` holds updates deliberately.** Pods
   with an ordinal below the partition are not updated at all — a stalled
   rollout may be a canary working exactly as configured.

## Decision Tree
`decision-trees/storage.yaml` when the blocked ordinal's PVC is unbound;
`decision-trees/pod-failure.yaml` when the pod exists but is unready.

## Evidence to Collect
- Ordinal of the first non-ready pod; everything above it is a consequence.
- PVC status for that ordinal, and the StorageClass it requests.
- Readiness probe definition and its recent failures.
- `updateStrategy`, including `partition`.
- `podManagementPolicy` — `Parallel` changes all of the above.
- Node the previous ordinal ran on, if the volume is zone-bound.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| Ordinal N Pending, PVC Pending | Storage cannot provision — later ordinals blocked behind it | High |
| Ordinal N Running but not Ready | Readiness probe failing; `OrderedReady` halts the rollout | High |
| Rollout stopped at a specific ordinal | `partition` set in `updateStrategy` | High |
| Pod cannot schedule after a node failure | Volume node affinity pins it to a dead node or zone | High |
| Data unexpectedly present after scale-down and up | PVCs are retained by design | High |
| Template change rejected | `volumeClaimTemplates` is immutable | High |

## Confirmation
Confirm the ordering hypothesis by verifying the readiness of the ordinal below
the stuck one:

```bash
kubectl get pod <name>-<ordinal-1> -n <namespace> \
  -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}{"\n"}'
```

`False` confirms the rollout is blocked by ordering rather than by the stuck
pod's own configuration.

## Remediation
Fix the blocking ordinal's underlying cause — provision its volume, repair its
readiness probe, or free capacity in its zone. Advance or clear `partition` to
release a held rollout. Where startup order genuinely does not matter, switching
to `podManagementPolicy: Parallel` prevents one pod from blocking the rest, but
this must be a deliberate choice for the workload.

## Blast Radius
StatefulSet changes proceed one ordinal at a time and can take a long while.
Deleting a PVC destroys that ordinal's data permanently. Switching to
`podManagementPolicy: Parallel` changes startup ordering for every replica,
which some clustered applications depend on for correctness.

## Human Approval Required
- `kubectl rollout restart statefulset/<name> -n <namespace>`
- `kubectl patch statefulset <name> -n <ns> -p '{"spec":{"updateStrategy":{"rollingUpdate":{"partition":0}}}}'`
- `kubectl delete pvc <claim> -n <namespace>` — **DESTRUCTIVE**, destroys the volume's data

## Verification
```bash
kubectl get statefulset <name> -n <namespace>
kubectl get pods -n <namespace> -l app=<label> --sort-by=.metadata.name
```
Verified when `READY` matches the desired replica count and every ordinal is
Running and Ready in sequence. Check the application's own clustering state too
— a quorum-based system can have all pods Ready and still be unhealthy.

## Rollback
`kubectl rollout undo statefulset/<name>` restores the previous template.
Deleted PVCs cannot be restored. `podManagementPolicy` is immutable, so
reversing it requires recreating the StatefulSet.

## Related Runbooks
- [../storage/pvc-pending.md](../storage/pvc-pending.md)
- [../pods/probes.md](../pods/probes.md)
- [../pods/pending.md](../pods/pending.md)
- [../storage/multi-attach.md](../storage/multi-attach.md)

## Official Documentation
- [StatefulSets](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)
- [StatefulSet Basics](https://kubernetes.io/docs/tutorials/stateful-application/basic-stateful-set/)
