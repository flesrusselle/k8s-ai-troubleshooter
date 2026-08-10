# Evicted Pods Runbook

## Purpose
Diagnose pods evicted from host nodes due to node resource pressure (DiskPressure, MemoryPressure).

## When to Use
Triggered when pod status reports `Evicted`.

## Safety Level
`SAFE_READ`

## Symptoms
- Pod status displays `Evicted`.
- Multiple pods terminated simultaneously on the same host node.

## Quick Diagnosis

```bash
# 1. List evicted pods in namespace
kubectl get pods -n <namespace> --field-selector status.phase=Failed

# 2. Inspect eviction reason and message
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.status.reason}{"\t"}{.status.message}{"\n"}'
```

## Detailed Investigation

1. **Check Eviction Reason**:
   - `The node was low on resource: ephemeral-storage`: Container log directory or `emptyDir` filled node disk.
   - `The node was low on resource: memory`: Node memory threshold breached.
2. **Inspect Host Node Health**:
   ```bash
   kubectl describe node <node-name>
   ```

## Decision Tree
`decision-trees/node-health.yaml`

## Evidence to Collect
- Eviction message text (`status.message`).
- Host node condition flags (`DiskPressure`, `MemoryPressure`).
- Ephemeral storage requests/limits in pod spec.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| `low on resource: ephemeral-storage` | Uncapped application logging to stdout or large temporary files in `emptyDir` | High |
| `low on resource: memory` | Node-level memory exhaustion | High |

## Confirmation
Confirm node disk/memory consumption at the host level.

## Remediation
Clean host logs, set `ephemeral-storage` resource limits on containers, or expand node disk.

## Human Approval Required
- `kubectl delete pod --field-selector status.phase=Failed -n <namespace>`
- Node cleanup commands.

## Related Runbooks
- [node-pressure.md](../nodes/node-pressure.md)

## Official Documentation
- [Node Pressure Eviction](https://kubernetes.io/docs/concepts/scheduling-eviction/node-pressure-eviction/)
