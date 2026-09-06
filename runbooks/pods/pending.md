# Pending Pods Runbook

## Purpose
Diagnose pods stuck in `Pending` phase that cannot be scheduled onto cluster nodes.

## When to Use
Triggered when pod status remains `Pending` without transitioning to `Running` or `ContainerCreating`.

## Safety Level
`SAFE_READ`

## Symptoms
- Pod status: `Pending`.
- Warning events from `default-scheduler`.

## Quick Diagnosis

```bash
# 1. Fetch scheduler decision events
kubectl describe pod <pod-name> --namespace <namespace>

# 2. Check PVC binding status (if pod requests storage)
kubectl get pvc --namespace <namespace>

# 3. Check cluster resource capacity vs requested resources
kubectl describe nodes | grep -E "Allocated resources|Resource" -A 8
```

## Detailed Investigation

Traverse scheduling constraint categories:

```text
Pending Pod
    ├── Resource Constraints (Insufficient CPU/Memory)
    ├── PVC Binding (`WaitForFirstConsumer`)
    ├── Node Selectors / Affinity / Anti-Affinity mismatch
    ├── Taints & Tolerations (Node has taint pod cannot tolerate)
    └── ResourceQuota / LimitRange exceeded in namespace
```

1. **Inspect Events**:
   Read scheduler failure reasons (e.g. `0/3 nodes are available: 3 Insufficient memory`).
2. **Check Unbound PVCs**:
   If pod uses a PVC, ensure PVC is `Bound`.
3. **Inspect Namespace Quotas**:
   ```bash
   kubectl get resourcequotas --namespace <namespace>
   ```

## Decision Tree
`decision-trees/pod-failure.yaml`

## Evidence to Collect
- Scheduler warning event output.
- Pod CPU and memory requests (`spec.containers[*].resources.requests`).
- Node taints (`spec.taints`) and pod tolerations (`spec.tolerations`).
- PVC binding state.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| `0/N nodes available: Insufficient memory` | Cluster nodes out of memory capacity | High |
| `unbound immediate PersistentVolumeClaim` | PVC not bound to PV | High |
| `node(s) had untolerated taint` | Node has taint not matched in pod tolerations | High |

## Confirmation
Confirm root cause by verifying scheduler event against node capacity or pod spec.

## Remediation
Scale up node pool, lower pod resource requests, or add missing tolerations.

## Blast Radius
Adding nodes changes cluster cost immediately. Lowering resource requests to
make a pod fit affects scheduling for every replica and can cause CPU throttling
or OOMKills later — it moves the failure rather than removing it.

## Human Approval Required
- `kubectl scale deployment/<name> --replicas=N`
- Provision additional cloud nodes.

## Verification
```bash
kubectl get pod <pod-name> --namespace <namespace> -o wide
```
Verified when the pod shows a `NODE` assignment and leaves `Pending`. Confirm no
other workload was displaced: re-run the cluster-wide Pending query and check
the count has genuinely gone down rather than moved.

## Rollback
Scale the node group back down, or restore the original resource requests.
Nodes added during an incident should be removed deliberately afterwards —
autoscalers frequently will not reclaim them while any pod tolerates them.

## Related Runbooks
- [pvc-pending.md](../storage/pvc-pending.md)
- [node-pressure.md](../nodes/node-pressure.md)

## Official Documentation
- [Kubernetes Pod Scheduling](https://kubernetes.io/docs/concepts/scheduling-eviction/kube-scheduler/)
