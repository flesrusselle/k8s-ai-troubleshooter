# Find All Failing Pods Runbook

## Purpose
Systematically discover, filter, and inspect all failing, non-running, or restarting pods across all Kubernetes namespaces.

## When to Use
Triggered when the user asks:
- "Find all failing pods."
- "Check why my pod is failing."
- "Show me all unhealthy workloads in the cluster."

## Safety Level
`SAFE_READ`

## Symptoms
- Pods in state `CrashLoopBackOff`, `OOMKilled`, `ImagePullBackOff`, `ErrImagePull`, `Pending`, `ContainerCreating`, `Evicted`, `Error`, or `Unknown`.
- High restart counts in container status.

## Quick Diagnosis

```bash
# Query all namespaces for non-running pods
kubectl get pods -A --field-selector=status.phase!=Running,status.phase!=Succeeded

# Filter pods with container exit details via JSONPath
kubectl get pods -A -o jsonpath='{range .items[*]}{.metadata.namespace}{"\t"}{.metadata.name}{"\t"}{range .status.containerStatuses[*]}{.name}{" restarts="}{.restartCount}{" state="}{.state}{"\n"}{end}{end}'
```

## Detailed Investigation

1. **Scan All Namespaces**: Always pass `-A` unless a specific namespace is requested.
2. **Classify Pod Failure Modes**:
   - **CrashLoopBackOff**: Container starts, exits with non-zero code, and restarts repeatedly.
   - **OOMKilled**: Container exceeded memory limit (`exit code 137`).
   - **ImagePullBackOff**: Image registry fetch failed.
   - **Pending**: Scheduler cannot place pod on any node.
   - **Evicted**: Host node evicted pod due to Disk/Memory pressure.
3. **Inspect Owner References**:
   Determine if the failing pod belongs to a `Deployment`, `StatefulSet`, `DaemonSet`, or `Job`:
   ```bash
   kubectl get pod <pod-name> --namespace <namespace> -o jsonpath='{.metadata.ownerReferences}'
   ```

## Decision Tree
`decision-trees/pod-failure.yaml`

## Evidence to Collect
- Pod namespace and name.
- Container state (waiting, running, terminated).
- Last exit code and termination reason.
- Restart count.
- Owning workload type and name.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| `CrashLoopBackOff` + Exit Code 1 | Application code exception or missing configuration | High |
| `OOMKilled` + Exit Code 137 | Container memory limit exceeded | High |
| `ImagePullBackOff` | Wrong image tag or missing `imagePullSecrets` | High |
| `Pending` + `0/X nodes available` | Resource quota or CPU/Memory constraint | High |

## Confirmation
Confirm failure reason by running `kubectl describe pod` and checking recent events.

## Remediation
Refer to specific pod failure runbook (e.g. `crashloopbackoff.md`, `oomkilled.md`).

## Blast Radius
None — this runbook only surveys. Each failure it finds carries the blast
radius of its own remediation.

## Human Approval Required
Any workload restart or spec modification requires explicit human approval.

## Verification
```bash
kubectl get pods --all-namespaces --field-selector=status.phase!=Running
```
Verified when the failing set is empty, or when every remaining entry is
explained and expected — `Completed` Job pods are not failures. Compare against
the count you started with rather than judging the list in isolation.

## Rollback
Nothing to roll back. If the survey missed failures, widen it: pods that are
`Running` but not `Ready` do not appear under a phase filter and must be found
by comparing the `READY` column.

## Related Runbooks
- [crashloopbackoff.md](crashloopbackoff.md)
- [oomkilled.md](oomkilled.md)
- [imagepullbackoff.md](imagepullbackoff.md)

## Official Documentation
- [Pod Lifecycle Documentation](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/)
