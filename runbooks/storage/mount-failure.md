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
kubectl describe pod <pod-name> -n <namespace>

# 2. Inspect active VolumeAttachments
kubectl get volumeattachments
```

## Detailed Investigation

1. **Check ReadWriteOnce (RWO) Lock**:
   If volume access mode is `ReadWriteOnce`, cloud block stores (EBS, GPD) can only attach to one host node at a time. If previous pod on Node A did not release volume before Node B requested attachment, mount blocks.
2. **Check Node CSI Plugin**:
   Verify CSI node daemon set pods are healthy:
   ```bash
   kubectl get pods -n kube-system -l app=csi-node || true
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

## Human Approval Required
- Force delete old pod or detach VolumeAttachment.

## Related Runbooks
- [pvc-pending.md](pvc-pending.md)

## Official Documentation
- [Volume Snapshots & CSI Mounts](https://kubernetes.io/docs/concepts/storage/volumes/)
