# High Restart Count Runbook

## Purpose
Investigate pods exhibiting high restart counts that eventually stabilize or cycle periodically.

## When to Use
Triggered when container restart count is elevated (e.g. > 10) despite pod currently showing `Running`.

## Safety Level
`SAFE_READ`

## Symptoms
- Pod phase: `Running` but `RESTARTS` column shows high value (e.g. 42).
- Intermittent application latency or dropped connections.

## Quick Diagnosis

```bash
# 1. Sort pods by restart count in namespace
kubectl get pods -n <namespace> -o jsonpath='{range .items[*]}{.metadata.name}{"\tRestarts="}{range .status.containerStatuses[*]}{.restartCount}{" "}{end}{"\n"}{end}' | sort -k2 -n -r

# 2. Inspect container last state termination history
kubectl describe pod <pod-name> -n <namespace>
```

## Detailed Investigation

1. **Inspect Last Termination Reason**:
   Determine if restarts are driven by periodic OOMKills, intermittent liveness probe timeouts, or background job completion exit.
2. **Review Chronological Events**:
   ```bash
   kubectl get events -n <namespace> --field-selector involvedObject.name=<pod-name> --sort-by='.metadata.creationTimestamp'
   ```

## Decision Tree
`decision-trees/pod-failure.yaml`

## Evidence to Collect
- Historical restart count trend.
- `lastState.terminated` exit code and timestamp.
- Application error logs preceding restarts.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| Periodic restart every 1 hour | Scheduled cron memory leak or strict liveness probe interval | Medium |
| High restarts on batch initContainer | Upstream dependency timeout on startup | High |

## Confirmation
Match termination timestamps with application log entries or resource spikes.

## Remediation
Fix underlying instability, increase resource limits, or tune probe thresholds.

## Blast Radius
Depends entirely on the cause found. Restart churn is a symptom; the
remediation belongs to whichever runbook the underlying cause routes to, and
carries that runbook's blast radius.

## Human Approval Required
- Deployment rollout restart or manifest update.

## Verification
```bash
kubectl get pods -n <namespace> \
  -o custom-columns='POD:.metadata.name,RESTARTS:.status.containerStatuses[0].restartCount'
```
Verified when the restart count is stable across an interval longer than the
previous mean time between restarts. Record the count and the time; a count that
has not moved in five minutes proves nothing about a pod that restarted hourly.

## Rollback
Roll back whatever change was applied. Restart *history* is not reversible —
the counter only resets when the pod object is replaced, so a high count on a
now-healthy pod is not evidence of an ongoing problem.

## Related Runbooks
- [crashloopbackoff.md](crashloopbackoff.md)
- [probes.md](probes.md)

## Official Documentation
- [Pod Lifecycle Overview](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/)
