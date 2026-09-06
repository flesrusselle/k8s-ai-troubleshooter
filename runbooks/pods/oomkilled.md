# OOMKilled Runbook

## Purpose
Diagnose pods terminated due to Out Of Memory (`OOMKilled`, exit code 137).

## When to Use
Triggered when container state displays `OOMKilled` or last termination reason is `OOMKilled`.

## Safety Level
`SAFE_READ`

## Symptoms
- Container terminated with exit code 137.
- Pod status: `OOMKilled` or `CrashLoopBackOff`.
- Restart count incrementing under memory-intensive workloads.

## Quick Diagnosis

```bash
# 1. Inspect container termination reason
kubectl get pod <pod-name> --namespace <namespace> -o jsonpath='{.status.containerStatuses[*].lastState.terminated}'

# 2. Check memory limits vs requests
kubectl get pod <pod-name> --namespace <namespace> -o jsonpath='{range .spec.containers[*]}{.name}{" Limit="}{.resources.limits.memory}{" Request="}{.resources.requests.memory}{"\n"}{end}'

# 3. Check node memory pressure (requires Metrics Server if using top)
kubectl top pod <pod-name> --namespace <namespace> --containers || true
```

## Detailed Investigation

1. **Verify Termination Reason**:
   Confirm container was killed by Linux OOM killer (`exitCode: 137`, `reason: OOMKilled`).
2. **Inspect Configured Memory Limits**:
   Compare container memory limit against application runtime requirements (e.g. JVM heap size setting `-Xmx` vs container limit).
3. **Check Node Memory Pressure**:
   Check if host node is experiencing `MemoryPressure`:
   ```bash
   kubectl describe node <node-name>
   ```

## Decision Tree
`decision-trees/pod-failure.yaml`

## Evidence to Collect
- Configured container memory limits and requests.
- Peak memory usage prior to crash.
- JVM / runtime heap configuration parameters.
- Host node `MemoryPressure` status.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| `OOMKilled` + limit = 256Mi | Memory limit set too low for workload | High |
| JVM `-Xmx` exceeds container memory limit | Java heap exceeds cgroup memory boundary | High |
| Gradual memory increase until 137 | Application memory leak | High |

## Confirmation
Confirm that container peak memory exceeded the configured `resources.limits.memory` cgroup boundary.

## Remediation
Increase container memory limits in deployment spec or Helm values, or optimize application memory footprint.

## Blast Radius
Raising a memory limit changes the pod's QoS class and its scheduling
footprint: it may no longer fit on its current node, and the rollout can leave
pods Pending if the cluster lacks headroom. Raising limits namespace-wide can
exhaust a ResourceQuota and block unrelated deployments.

## Human Approval Required
- `kubectl set resources deployment/<deployment-name> -c=<container-name> --limits=memory=1Gi --namespace <namespace>`
- `helm upgrade <release-name> <chart> -f values.yaml`

## Verification
```bash
kubectl get pod <pod-name> --namespace <namespace> \
  -o jsonpath='{.status.containerStatuses[*].lastState.terminated.reason}{"\n"}'
kubectl top pod <pod-name> --namespace <namespace> --containers
```
Verified when `lastState.terminated.reason` is no longer `OOMKilled` after a
full workload cycle, and steady-state usage sits comfortably below the new
limit. Check under real load — a limit that holds at 3am proves nothing.

## Rollback
Reapply the previous limits with `kubectl rollout undo`. If the true cause was
a memory leak rather than an undersized limit, rolling back returns you to
OOMKills on the original schedule — the leak is the fix, not the limit.

## Related Runbooks
- [crashloopbackoff.md](crashloopbackoff.md)
- [node-pressure.md](../nodes/node-pressure.md)

## Official Documentation
- [Resource Management for Pods](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)
