# NodeNotReady Diagnostic Runbook

## Purpose
Diagnose Kubernetes host nodes marked as `NotReady` by the control plane.

## When to Use
Triggered when `kubectl get nodes` displays `NotReady` status for one or more worker nodes.

## Safety Level
`SAFE_READ`

## Symptoms
- Node status: `NotReady`.
- Workloads evicted or rescheduled from node.

## Quick Diagnosis

```bash
# 1. Fetch detailed node status conditions
kubectl describe node <node-name>

# 2. Check Node lifecycle events
kubectl get events -A --field-selector involvedObject.kind=Node --sort-by='.metadata.creationTimestamp'
```

## Detailed Investigation

Inspect Node Conditions:

```text
NodeConditions
  ├── KubeletReady: False -> Kubelet daemon crashed or host systemd hung
  ├── MemoryPressure: True -> Host physical RAM exhausted
  ├── DiskPressure: True -> Host disk /var/lib/docker or /var/lib/containerd full
  └── NetworkUnavailable: True -> CNI plugin disconnected or route missing
```

1. **Verify Kubelet Status**: Check if `KubeletReady` condition is `False` or `Unknown`.
2. **Verify Network Connectivity**: Check if host node lost heartbeat communication with API server.

## Decision Tree
`decision-trees/node-health.yaml`

## Evidence to Collect
- `kubectl describe node` condition flags.
- Node creation age and kernel version.
- System warning events.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| `KubeletReady = Unknown` | Network partitioning between worker node and control plane | High |
| `KubeletReady = False` + `DiskPressure` | Host disk full causing kubelet container runtime eviction | High |

## Confirmation
Confirm whether node issue is localized to host kubelet/disk vs network partition.

## Remediation
Restart host `kubelet` daemon, clean host container image cache, or reboot host VM.

## Human Approval Required
- `kubectl cordon <node-name>`
- `kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data`

## Related Runbooks
- [node-pressure.md](file:///Users/flestorres/Desktop/apply/k8s-ai-troubleshooter/runbooks/nodes/node-pressure.md)
- [cluster-health.md](file:///Users/flestorres/Desktop/apply/k8s-ai-troubleshooter/runbooks/cluster/cluster-health.md)

## Official Documentation
- [Node Status Documentation](https://kubernetes.io/docs/concepts/architecture/nodes/#status)
