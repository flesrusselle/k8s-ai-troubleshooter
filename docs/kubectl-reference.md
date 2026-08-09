# kubectl & JSONPath Cheat Sheet

Practical, tested `kubectl` JSONPath commands for rapid cluster diagnosis.

---

## 🔍 Pod & Workload Queries

```bash
# Get all non-running pods across all namespaces
kubectl get pods -A --field-selector=status.phase!=Running

# List failing pods with container exit code and termination reason
kubectl get pods -A -o jsonpath='{range .items[*]}{.metadata.namespace}{"\t"}{.metadata.name}{"\t"}{range .status.containerStatuses[*]}{.name}{" state="}{.state}{" exitCode="}{.lastState.terminated.exitCode}{" reason="}{.lastState.terminated.reason}{"\n"}{end}{end}'

# List pod restart counts across cluster
kubectl get pods -A -o jsonpath='{range .items[*]}{.metadata.namespace}{"\t"}{.metadata.name}{"\t"}{range .status.containerStatuses[*]}{.name}{" restarts="}{.restartCount}{"\n"}{end}{end}'

# Extract resource limits & requests for a specific pod
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{range .spec.containers[*]}{.name}{" CPU limit="}{.resources.limits.cpu}{" Mem limit="}{.resources.limits.memory}{"\n"}{end}'
```

---

## 📌 Node & Event Queries

```bash
# Get nodes with status and taints
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\tStatus="}{.status.conditions[-1].type}{"="}{.status.conditions[-1].status}{"\tTaints="}{.spec.taints}{"\n"}{end}'

# Get cluster-wide warning events sorted by timestamp
kubectl get events -A --field-selector type=Warning --sort-by='.metadata.creationTimestamp'
```
