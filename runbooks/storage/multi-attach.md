# Multi-Attach Volume Error Runbook

## Purpose
Diagnose pods blocked by `Multi-Attach error for volume`, where a ReadWriteOnce
volume is still attached to another node.

## When to Use
Events show `Multi-Attach error for volume "pvc-..." Volume is already
exclusively attached to one node and can't be attached to another`.

## Safety Level
`SAFE_READ`

## Symptoms
- Pod stuck in `ContainerCreating` for 6+ minutes after a node failure.
- `Multi-Attach error for volume` in pod events.
- A rolling update of a stateful workload never completes.
- The old pod shows `Terminating` and does not clear.

## Quick Diagnosis

```bash
# 1. The error and its timing
kubectl describe pod <pod-name> --namespace <namespace>

# 2. Where the volume is currently attached
kubectl get volumeattachment | grep <pv-name>

# 3. Is the previous pod still holding it?
kubectl get pods -A -o wide | grep <pvc-name>

# 4. Access mode — this is the root of the constraint
kubectl get pvc <claim> --namespace <namespace> \
  -o jsonpath='{.spec.accessModes}{"\t"}{.spec.volumeName}{"\n"}'
```

## Detailed Investigation

```text
Multi-Attach error
       ↓
Is the old pod still running or Terminating?
       ↓ running    → two pods genuinely want one RWO volume
       ↓ Terminating → detach is in progress; usually resolves in ~6 minutes
       ↓ gone
Is the node it ran on healthy?
       ↓ no  → the volume cannot be detached cleanly from a dead node
       ↓ yes
Is there a stale VolumeAttachment?
       → the CSI driver failed to complete detachment
```

1. **ReadWriteOnce means one node, not one pod.** Several pods on the *same* node
   can share an RWO volume. The constraint is nodal, which is why this error
   appears specifically when a pod is rescheduled elsewhere.
2. **The six-minute figure is not arbitrary.** After a node becomes unreachable,
   Kubernetes waits before force-detaching. Pods rescheduled during that window
   see this error and then recover on their own — so the correct first action is
   often to wait and confirm, not to intervene.
3. **`Recreate` versus `RollingUpdate` decides whether this happens at all.** A
   RollingUpdate on an RWO-backed Deployment tries to start the new pod before
   the old one is gone. If they land on different nodes, they deadlock: the new
   pod waits for a volume the old pod will not release until the new pod is
   ready. `strategy: Recreate` is the correct setting for RWO workloads.
4. **A stuck `Terminating` pod holds the volume.** Finalizers, a hung container
   runtime, or a lost node all keep the attachment alive.
5. **`ReadWriteMany` avoids the class of problem entirely**, but requires a
   backing store that supports it — NFS, CephFS, EFS. Most block storage
   (EBS, Azure Disk, GCE PD) cannot.

## Decision Tree
`decision-trees/storage.yaml`

## Evidence to Collect
- Full `Multi-Attach` event with the PV name and how long ago it started.
- `VolumeAttachment` objects referencing that PV, and the node each names.
- State of the previous pod: Running, Terminating, or gone.
- Health of the node holding the attachment.
- PVC `accessModes` and the Deployment's `strategy`.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| Node failed, error under 6 minutes old | Normal detach timeout — wait | High |
| Old pod `Terminating` and not clearing | Finalizer or hung runtime holding the volume | High |
| RollingUpdate on an RWO-backed Deployment | Old and new pods deadlocked over one volume | High |
| Node gone, `VolumeAttachment` remains | CSI driver failed to detach from a dead node | High |
| Two Deployments mounting one PVC | Design error — RWO cannot span nodes | High |
| Recurs on every deploy | Strategy should be `Recreate` | High |

## Confirmation
Confirm which node still holds the volume:

```bash
kubectl get volumeattachment \
  -o custom-columns='NAME:.metadata.name,PV:.spec.source.persistentVolumeName,NODE:.spec.nodeName,ATTACHED:.status.attached' \
  | grep <pv-name>
```

If the named node no longer exists or is `NotReady`, the attachment is stale and
will not clear without intervention. If the node is healthy and running the old
pod, the fix is to remove that pod, not the attachment.

## Remediation
Wait out the detach timeout first — most cases resolve unattended. If a pod is
stuck `Terminating`, resolve its finalizer or runtime hang. For workloads that
hit this on every deploy, set `strategy: Recreate`. Where genuine concurrent
access is required, move to a `ReadWriteMany` storage class.

## Blast Radius
Force-deleting a pod that still holds a volume risks filesystem corruption if
the original writer is alive — this is one of the few remediations in this
repository that can destroy data rather than availability. Changing strategy to
`Recreate` means every future deploy has downtime by design.

## Human Approval Required
- `kubectl delete pod <stuck-pod> --namespace <namespace>` — **DESTRUCTIVE**, and forcing it can risk data corruption if the old writer is still alive
- `kubectl patch deployment <name> --namespace <ns> -p '{"spec":{"strategy":{"type":"Recreate"}}}'`
- `kubectl delete volumeattachment <name>` — **DESTRUCTIVE**, only for a confirmed-dead node; deleting a live attachment can corrupt the filesystem

## Verification
```bash
kubectl get volumeattachment | grep <pv-name>
kubectl get pod <pod-name> --namespace <namespace> -o wide
```
Verified when exactly one `VolumeAttachment` exists for the volume, naming the
node the running pod is on, and the pod is `Running`. Two attachments, or one
naming a node with no pod, means the situation is not resolved.

## Rollback
A deleted `VolumeAttachment` is recreated automatically by the attach
controller when the volume is legitimately needed. Data corrupted by a
concurrent-writer force-detach is **not** recoverable — restore from backup.
Reverting `strategy` to `RollingUpdate` reinstates the deadlock.

## Related Runbooks
- [mount-failure.md](mount-failure.md)
- [pvc-pending.md](pvc-pending.md)
- [../workloads/statefulset-stuck.md](../workloads/statefulset-stuck.md)
- [../nodes/node-not-ready.md](../nodes/node-not-ready.md)

## Official Documentation
- [Persistent Volumes — Access Modes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/#access-modes)
- [Storage Capacity and Attachment](https://kubernetes.io/docs/concepts/storage/storage-capacity/)
