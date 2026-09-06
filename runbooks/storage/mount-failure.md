# Volume Attachment & Mount Failure Runbook

## Purpose
Diagnose pods stuck in `ContainerCreating` state due to volume attachment or filesystem mount failures.

## When to Use
Triggered when pod events indicate `FailedMount` or `VolumeAttachment` timeouts.

## Safety Level
`SAFE_READ`

## Symptoms
- Pod phase: `ContainerCreating`.
- Event message: `Unable to attach or mount volumes: unattached volumes=[data], failed to process volumes=[data]: timed out waiting for the condition`.

## Quick Diagnosis

```bash
# 1. Inspect pod events for mount errors
kubectl describe pod <pod-name> --namespace <namespace>

# 2. Inspect active VolumeAttachments
kubectl get volumeattachments
```

## Detailed Investigation

1. **Check ReadWriteOnce (RWO) Lock**:
   If volume access mode is `ReadWriteOnce`, cloud block stores (EBS, GPD) can only attach to one host node at a time. If previous pod on Node A did not release volume before Node B requested attachment, mount blocks.
2. **Check Node CSI Plugin**:
   Verify CSI node daemon set pods are healthy:
   ```bash
   kubectl get pods --namespace kube-system -l app=csi-node || true
   ```

## Decision Tree
`decision-trees/storage.yaml`

## Evidence to Collect
- Pod mount failure event logs.
- VolumeAttachment objects status.
- AccessMode (`ReadWriteOnce`, `ReadWriteMany`).

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| `Multi-Attach error for volume` | Volume locked by old node prior to pod rescheduling | High |
| `corrupted filesystem` | Filesystem integrity error on host volume block device | High |

## Confirmation
Verify if the volume is attached to an offline/stuck host node.

## Remediation
Gracefully terminate previous pod instance or detach VolumeAttachment object.

## Blast Radius
Creating the missing Secret or ConfigMap affects every pod that references it.
Changing volume configuration replaces all pods in the workload and, for
stateful workloads, may require the volume to detach cleanly first.

## Human Approval Required
- Force delete old pod or detach VolumeAttachment.

## Verification
```bash
kubectl describe pod <pod-name> --namespace <namespace> | grep -A5 -E 'Volumes|Events'
```
Verified when the pod leaves `ContainerCreating` and no `FailedMount` events
appear for a period longer than the mount timeout — roughly two minutes. Mount
failures retry, so a single clean sample is not sufficient.

## Rollback
Revert the volume configuration with `kubectl rollout undo`. Data already
written to a newly mounted volume stays there. A Secret created to satisfy the
mount can be deleted, which returns the pod to its original failure.

## Related Runbooks
- [pvc-pending.md](pvc-pending.md)

## Official Documentation
- [Volume Snapshots & CSI Mounts](https://kubernetes.io/docs/concepts/storage/volumes/)
