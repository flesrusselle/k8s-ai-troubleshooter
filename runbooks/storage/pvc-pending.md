# PVC Pending & Provisioning Failure Runbook

## Purpose
Diagnose PersistentVolumeClaims (PVC) stuck in `Pending` phase or failing to dynamically provision storage.

## When to Use
Triggered when a PVC is not bound or pods mounting storage remain in `Pending` phase.

## Safety Level
`SAFE_READ`

## Symptoms
- PVC status: `Pending`.
- Pod stuck in `Pending` with event `unbound immediate PersistentVolumeClaim`.

## Quick Diagnosis

```bash
# 1. Fetch PVC status & events
kubectl describe pvc <pvc-name> -n <namespace>

# 2. Check cluster StorageClasses
kubectl get storageclass

# 3. Check CSI provisioner pod status
kubectl get pods -A -l app.kubernetes.io/component=csi-driver || true
```

## Detailed Investigation

1. **Check Specified StorageClass**:
   If PVC specifies `storageClassName`, verify it exists:
   ```bash
   kubectl get storageclass <sc-name>
   ```
2. **Check Volume Binding Mode**:
   - `Immediate`: Storage provisioner immediately creates PV upon PVC creation.
   - `WaitForFirstConsumer`: Storage provisioner waits until pod is scheduled to bind volume in matching node zone.

## Decision Tree
`decision-trees/storage.yaml`

## Evidence to Collect
- PVC spec requested capacity and access mode.
- PVC events.
- StorageClass configuration.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| `storageclass.storage.k8s.io not found` | StorageClass missing in cluster | High |
| `waiting for first consumer` | Normal state; pod must be scheduled before PVC binds | High |
| `exceeded quota` | Namespace StorageQuota limit reached | High |

## Confirmation
Confirm whether StorageClass exists and CSI provisioner plugin is active.

## Remediation
Create missing StorageClass, request supported capacity, or schedule consuming pod.

## Blast Radius
Creating a PV or changing a StorageClass affects future claims across the
cluster. Deleting and recreating a PVC destroys its data irreversibly if the
reclaim policy is `Delete`.

## Human Approval Required
- `kubectl delete pvc <name>` (**DESTRUCTIVE — ABSOLUTE HUMAN APPROVAL REQUIRED**)
- `kubectl apply -f storageclass.yaml`

## Verification
```bash
kubectl get pvc <claim> -n <namespace>
```
Verified when `STATUS` reads `Bound` and the consuming pod leaves `Pending`.
With `WaitForFirstConsumer`, a Pending PVC is expected until a pod schedules —
verify the pod, not the claim.

## Rollback
A newly created PV can be deleted if unused. A deleted PVC cannot be restored:
with `reclaimPolicy: Delete` the underlying volume is destroyed with it. Confirm
the reclaim policy before treating any PVC deletion as reversible.

## Related Runbooks
- [mount-failure.md](mount-failure.md)
- [pending.md](../pods/pending.md)

## Official Documentation
- [Persistent Volumes Documentation](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)
