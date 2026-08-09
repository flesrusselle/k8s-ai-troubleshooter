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

## Human Approval Required
- `kubectl delete pvc <name>` (**DESTRUCTIVE — ABSOLUTE HUMAN APPROVAL REQUIRED**)
- `kubectl apply -f storageclass.yaml`

## Related Runbooks
- [mount-failure.md](file:///Users/flestorres/Desktop/apply/k8s-ai-troubleshooter/runbooks/storage/mount-failure.md)
- [pending.md](file:///Users/flestorres/Desktop/apply/k8s-ai-troubleshooter/runbooks/pods/pending.md)

## Official Documentation
- [Persistent Volumes Documentation](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)
