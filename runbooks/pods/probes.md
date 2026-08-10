# Readiness, Liveness & Startup Probes Failure Runbook

## Purpose
Diagnose readiness, liveness, and startup probe failures causing traffic detachment or container restarts.

## When to Use
Triggered when events report `Unhealthy` probes or pods fail readiness checks.

## Safety Level
`SAFE_READ`

## Symptoms
- Pod endpoints detached from Service (`Endpoints` missing pod IP).
- Container restarted with exit code 137 due to failed liveness probe.
- Events show `Readiness probe failed: HTTP probe failed with statuscode 500`.

## Quick Diagnosis

```bash
# 1. Fetch probe failure events
kubectl describe pod <pod-name> -n <namespace> | grep -E "Readiness|Liveness|Startup|Unhealthy" -A 2

# 2. Inspect configured probe settings in spec
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{range .spec.containers[*]}{.name}{"\nReadiness="}{.readinessProbe}{"\nLiveness="}{.livenessProbe}{"\nStartup="}{.startupProbe}{"\n"}{end}'
```

## Detailed Investigation

1. **Classify Probe Type**:
   - **Startup Probe**: Blocks readiness/liveness during application cold boot. Failure kills container.
   - **Liveness Probe**: Determines if container is alive. Failure triggers container restart.
   - **Readiness Probe**: Determines if container can receive network traffic. Failure removes pod IP from Service `Endpoints`.
2. **Inspect Probe Parameters**:
   Check `initialDelaySeconds`, `timeoutSeconds`, `periodSeconds`, `failureThreshold`, and HTTP health endpoint path.

## Decision Tree
`decision-trees/pod-failure.yaml`

## Evidence to Collect
- Probe configuration (type, path, port, thresholds).
- Probe failure HTTP status code or timeout event message.
- Application logs around probe execution window.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| Readiness probe HTTP 500 | Application DB connection failure during health check | High |
| Liveness timeout during startup | `initialDelaySeconds` too low for slow application cold start | High |
| Probe HTTP 404 | Wrong endpoint URL path configured in probe spec | High |

## Confirmation
Confirm probe failure reason by comparing application logs with probe execution timestamps.

## Remediation
Adjust probe delays/timeouts or fix application health endpoint handler.

## Blast Radius
Loosening a liveness probe reduces the cluster's ability to detect a genuinely
hung container — that is a real reduction in self-healing, not a free change.
Tightening one risks killing healthy pods under load. Both affect every replica.

## Human Approval Required
- Manifest update or `helm upgrade`.

## Verification
```bash
kubectl describe pod <pod-name> -n <namespace> | grep -A3 -E 'Liveness|Readiness'
kubectl get events -n <namespace> --field-selector reason=Unhealthy
```
Verified when no new `Unhealthy` events appear across a full traffic cycle
including peak. A probe that passes at low traffic and fails at peak has not
been fixed, and the failure will return with load.

## Rollback
Restore the previous probe definition with `kubectl rollout undo`. If the probe
was masking a slow-starting application, rolling back reinstates the restart
loop — the startup time is the underlying issue.

## Related Runbooks
- [endpoints.md](../networking/endpoints.md)
- [crashloopbackoff.md](crashloopbackoff.md)

## Official Documentation
- [Configure Liveness, Readiness and Startup Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
