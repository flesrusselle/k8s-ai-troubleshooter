# CrashLoopBackOff Runbook

## Purpose
Investigate and diagnose pods repeatedly crashing and entering the `CrashLoopBackOff` state.

## When to Use
Triggered when a pod status displays `CrashLoopBackOff` or container restart count is rapidly incrementing.

## Safety Level
`SAFE_READ`

## Symptoms
- Pod status: `CrashLoopBackOff`.
- High container restart count (e.g. > 5).
- Application service returning 502/503.

## Quick Diagnosis

```bash
# 1. Inspect pod container state and exit code
kubectl describe pod <pod-name> -n <namespace>

# 2. Fetch logs from previous failed instance
kubectl logs <pod-name> -n <namespace> --previous --all-containers

# 3. Check current logs
kubectl logs <pod-name> -n <namespace> --all-containers --tail=100
```

## Detailed Investigation

Follow the deterministic investigation path:

```text
CrashLoopBackOff
       ↓
Check Container Exit Code (`kubectl describe pod`)
       ↓
Exit Code 1/127 -> Check Previous Logs (`kubectl logs --previous`)
Exit Code 137 -> Check OOMKilled Runbook
       ↓
Inspect Application Startup Parameters & Environment Variables
       ↓
Inspect ConfigMap / Secret dependencies
       ↓
Check Helm Release Ownership (`helm list -A`)
```

1. **Check Exit Code**:
   - `Exit Code 1`: Application crash (uncaught exception, invalid configuration).
   - `Exit Code 127`: Command / binary not found inside container image.
   - `Exit Code 137`: Terminated by SIGKILL (OOMKilled or failed liveness probe).
   - `Exit Code 143`: Terminated by SIGTERM.
2. **Inspect Previous Logs**:
   Crucial step: `kubectl logs --previous` exposes stdout/stderr right before the crash.

## Decision Tree
`decision-trees/pod-failure.yaml`

## Evidence to Collect
- Last exit code and termination reason.
- Log error stack traces from `--previous`.
- Environment variable configuration values.
- Helm release management metadata.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| `Exit Code 1` + "DB connection failed" | Missing or invalid database secret / connection string | High |
| `Exit Code 127` + "entrypoint script not found" | Invalid Dockerfile CMD/ENTRYPOINT or missing executable permission | High |
| `Exit Code 137` | Out of Memory or Liveness Probe failure | High |

## Confirmation
Confirm root cause by verifying error stack trace in `--previous` logs against application code/configuration.

## Remediation
Update application configuration, fix environment secrets, or adjust container limits.

## Blast Radius
`rollout restart` replaces every pod in the Deployment, not just the crashing
one. Expect brief unavailability proportional to `maxUnavailable`. A config or
secret change affects every pod consuming it, which may include workloads you
are not looking at.

## Human Approval Required
- `kubectl rollout restart deployment/<deployment-name> -n <namespace>`
- `helm upgrade <release-name> <chart> -f values.yaml`

## Verification
```bash
kubectl get pod <pod-name> -n <namespace> -w
```
The restart count must stop climbing and the pod must reach `Running` and stay
there for longer than its previous crash interval. A pod that survives 30
seconds when it previously crashed in 2 has not necessarily recovered — compare
against the old lifetime, not against zero.

## Rollback
`kubectl rollout undo deployment/<name> -n <namespace>` returns the previous
pod template. It does not undo a ConfigMap or Secret edit, so if the fix was a
config change, revert that separately and restart again.

## Related Runbooks
- [oomkilled.md](oomkilled.md)
- [probes.md](probes.md)
- [helm-troubleshooting.md](../helm/helm-troubleshooting.md)

## Official Documentation
- [Kubernetes Pod Lifecycle - Container States](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#container-states)
