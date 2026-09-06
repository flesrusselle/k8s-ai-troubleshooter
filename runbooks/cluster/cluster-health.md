# Global Cluster Health Inspection Runbook

## Purpose
Guide SREs and AI assistants through a safe, cluster-wide health inspection without assuming prior knowledge of namespace names or workload placement.

## When to Use
Triggered when starting a diagnostic session, when a general incident is reported ("the cluster is down"), or prior to investigating specific workload anomalies.

## Safety Level
`SAFE_READ`

## Symptoms
- Cluster control plane or node unresponsiveness.
- Multiple applications reporting errors simultaneously.
- General user report: "Find all unhealthy pods in the cluster."

## Quick Diagnosis

```bash
# 1. Inspect control plane endpoints
kubectl cluster-info

# 2. Check all cluster node statuses
kubectl get nodes -o wide

# 3. Find failing pods across ALL namespaces
kubectl get pods -A --field-selector=status.phase!=Running,status.phase!=Succeeded

# 4. Check cluster-wide warning events
kubectl get events -A --field-selector type=Warning --sort-by='.metadata.creationTimestamp'
```

## Detailed Investigation

1. **Verify Active Cluster Context**:
   Ensure you are inspecting the intended cluster context:
   ```bash
   kubectl config current-context
   ```
2. **Inspect Core Component & Node Health**:
   Identify any nodes with `NotReady` status or active pressures (`DiskPressure`, `MemoryPressure`):
   ```bash
   kubectl get nodes
   kubectl describe node
   ```
3. **Cluster-wide Workload Scan**:
   Do NOT assume a single namespace. Query all namespaces (`-A`):
   ```bash
   kubectl get pods -A -o jsonpath='{range .items[?(@.status.phase!="Running")]}{.metadata.namespace}{"\t"}{.metadata.name}{"\t"}{.status.phase}{"\t"}{.status.containerStatuses[*].state}{"\n"}{end}'
   ```

## Decision Tree
`decision-trees/node-health.yaml` and `decision-trees/pod-failure.yaml`

## Evidence to Collect
- Active context name.
- Count of `NotReady` nodes.
- List of unhealthy pods by namespace, phase, and container exit state.
- Recent cluster `Warning` events.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| All nodes `NotReady` | Cloud infrastructure network outage or Control Plane CNI failure | High |
| Pods failing in `kube-system` | Core add-on failure (CoreDNS, kube-proxy, CNI plugin) | High |
| Pods stuck in `Pending` across multiple namespaces | Node capacity exhaustion or PVC provisioner outage | High |

## Confirmation
Verify whether node conditions or pod failures correlate across namespaces.

## Remediation
Varies based on isolated root cause (node repair, CNI restart, capacity addition).

## Blast Radius
Control plane changes affect every workload in the cluster. Nothing in this
runbook should be treated as routine; a mistaken component restart is a
cluster-wide outage.

## Human Approval Required
- `kubectl rollout restart daemonset --namespace kube-system`
- `kubectl cordon <node>` — stops new scheduling onto the node
- `kubectl drain <node>` — **DESTRUCTIVE**, evicts every pod on the node

## Verification
```bash
kubectl get --raw='/readyz?verbose'
kubectl get nodes
```
Verified when `/readyz` reports `ok` for every check and all nodes are `Ready`.
Confirm a real workload operation succeeds too — a healthy control plane that
cannot schedule pods is not a healthy cluster.

## Rollback
Control plane rollback is provider-specific and outside this repository's
scope. Restore from your cluster's documented recovery procedure; etcd state in
particular cannot be rolled back by reapplying manifests.

## Related Runbooks
- [find-failing-pods.md](../pods/find-failing-pods.md)
- [node-not-ready.md](../nodes/node-not-ready.md)

## Official Documentation
- [Kubernetes Cluster Information](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_cluster-info/)
- [Node Status Documentation](https://kubernetes.io/docs/concepts/architecture/nodes/#status)
