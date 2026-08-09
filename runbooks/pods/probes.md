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

## Human Approval Required
- Manifest update or `helm upgrade`.

## Related Runbooks
- [endpoints.md](file:///Users/flestorres/Desktop/apply/k8s-ai-troubleshooter/runbooks/networking/endpoints.md)
- [crashloopbackoff.md](file:///Users/flestorres/Desktop/apply/k8s-ai-troubleshooter/runbooks/pods/crashloopbackoff.md)

## Official Documentation
- [Configure Liveness, Readiness and Startup Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
