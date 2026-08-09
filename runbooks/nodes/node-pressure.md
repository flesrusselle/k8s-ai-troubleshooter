# Node Pressure (DiskPressure / MemoryPressure / PIDPressure) Runbook

## Purpose
Diagnose resource pressure conditions on host nodes triggering pod evictions.

## When to Use
Triggered when a node reports `MemoryPressure`, `DiskPressure`, or `PIDPressure`.

## Safety Level
`SAFE_READ`

## Symptoms
- Pod evictions across workloads on node.
- Host node status conditions set to `True`.

## Quick Diagnosis

```bash
# 1. Fetch node resource pressure conditions
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\tMemoryPressure="}{.status.conditions[?(@.type=="MemoryPressure")].status}{"\tDiskPressure="}{.status.conditions[?(@.type=="DiskPressure")].status}{"\tPIDPressure="}{.status.conditions[?(@.type=="PIDPressure")].status}{"\n"}{end}'

# 2. Check resource consumption on node
kubectl describe node <node-name> | grep -A 7 "Allocated resources"
```

## Detailed Investigation

1. **DiskPressure**: Host root disk or container runtime directory (`/var/lib/containerd`) passed eviction threshold (default 85%).
2. **MemoryPressure**: Host available memory dropped below eviction threshold (default 100Mi).
3. **PIDPressure**: Number of active Linux OS tasks exceeded max PID threshold.

## Decision Tree
`decision-trees/node-health.yaml`

## Evidence to Collect
- Node pressure flags.
- Node allocated vs capacity CPU/Memory percentages.
- Pod count on affected node.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| `DiskPressure == True` | Stale container image layer accumulation or oversized log files | High |
| `PIDPressure == True` | Container application leaking OS threads / process forks | High |

## Confirmation
Confirm host resource pressure metrics against kubelet eviction thresholds.

## Remediation
Prune unused container images, clear host log files, or expand volume size.

## Human Approval Required
- Host SSH cleanup commands or node replacement.

## Related Runbooks
- [evicted.md](file:///Users/flestorres/Desktop/apply/k8s-ai-troubleshooter/runbooks/pods/evicted.md)
- [node-not-ready.md](file:///Users/flestorres/Desktop/apply/k8s-ai-troubleshooter/runbooks/nodes/node-not-ready.md)

## Official Documentation
- [Node Pressure Eviction](https://kubernetes.io/docs/concepts/scheduling-eviction/node-pressure-eviction/)
