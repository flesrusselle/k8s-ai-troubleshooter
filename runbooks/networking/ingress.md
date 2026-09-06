# Ingress 502 / 503 / 504 Backend Failure Runbook

## Purpose
Diagnose HTTP 502 Bad Gateway, 503 Service Unavailable, and 504 Gateway Timeout errors returned by Kubernetes Ingress controllers.

## When to Use
Triggered when an application URL routed through Ingress fails with HTTP 50x errors.

## Safety Level
`SAFE_READ`

## Symptoms
- Ingress returns `502 Bad Gateway`, `503 Service Unavailable`, or `504 Gateway Timeout`.
- Web UI or API endpoint inaccessible.

## Quick Diagnosis

Trace the network request path step-by-step:

```text
Client -> Ingress -> Ingress Controller Pod -> Service -> Endpoints -> Application Pod
```

```bash
# 1. Inspect Ingress resource rules & backend target service
kubectl get ingress --namespace <namespace> -o wide

# 2. Check Ingress Controller pod health & logs
kubectl get pods --namespace ingress-nginx (or namespace of controller)
kubectl logs --namespace ingress-nginx -l app.kubernetes.io/name=ingress-nginx --tail=100

# 3. Verify backend Service and Endpoints
kubectl get svc,endpoints --namespace <namespace>
```

## Detailed Investigation

1. **HTTP 502 Bad Gateway**:
   - Ingress controller reached Service endpoint, but container refused connection or closed socket prematurely.
   - Check application container logs for crashes/panics.
2. **HTTP 503 Service Unavailable**:
   - Ingress controller cannot find any active endpoints for backend Service (`Endpoints` list empty).
   - Check [endpoints.md](endpoints.md).
3. **HTTP 504 Gateway Timeout**:
   - Application container taking longer to respond than Ingress proxy timeout setting (`proxy-read-timeout`).

## Decision Tree
`decision-trees/networking.yaml`

## Evidence to Collect
- Ingress controller log error line.
- Backend Service endpoint state.
- Backend pod container logs during request timestamp.
- Ingress annotations (proxy timeouts, backend protocol).

## Root Cause Patterns

| Error Code | Likely Cause | Confidence |
| :--- | :--- | :--- |
| HTTP 503 | Backend Service has 0 ready endpoints | High |
| HTTP 502 | Backend application crashed or TLS mismatch between Ingress and backend | High |
| HTTP 504 | Upstream application database query deadlock / timeout | High |

## Confirmation
Identify exact error code in Ingress controller log mapped to backend pod IP.

## Remediation
Fix backend application crash, adjust readiness probe, or update proxy timeout annotation.

## Blast Radius
Ingress changes affect every route on that host, and controller-level changes
affect every Ingress in the cluster. A bad annotation can take down unrelated
applications sharing the controller.

## Human Approval Required
- `kubectl annotate ingress <ingress-name> --namespace <namespace> ...`
- `helm upgrade <ingress-controller-release>`

## Verification
```bash
kubectl describe ingress <ingress> --namespace <namespace>
curl -sS -o /dev/null -w '%{http_code}\n' https://<host>/<path>
```
Verified when the expected status code is returned end-to-end from outside the
cluster, not just from inside it. Test the specific path that was failing —
another path on the same host proves nothing about this rule.

## Rollback
Reapply the previous Ingress manifest. Cached DNS and certificate state can
outlive the rollback, so allow for TTL before concluding it did not work.

## Related Runbooks
- [endpoints.md](endpoints.md)
- [probes.md](../pods/probes.md)

## Official Documentation
- [Ingress Controllers](https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/)
