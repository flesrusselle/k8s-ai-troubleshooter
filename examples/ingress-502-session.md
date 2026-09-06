# End-to-End Diagnostic Session: Ingress HTTP 502 / 503

Simulated AI-assisted troubleshooting session for Ingress routing failures.

---

## 👤 User Prompt
> "Why is my ingress returning HTTP 502 Bad Gateway for api.example.com?"

---

## 🤖 AI Assistant Response

```markdown
## Situation
User reports HTTP 502 Bad Gateway when accessing `api.example.com`.

## What I Checked
- `kubectl get ingress -A`
- `kubectl get svc --namespace production`
- `kubectl get endpoints api-service --namespace production`
- `kubectl describe pod --namespace production -l app=api`

## Evidence
1. Ingress `api-ingress` routes `api.example.com/` to backend service `api-service:8080`.
2. `kubectl get endpoints api-service` returns `<none>`.
3. Backing pods for `app=api` are failing readiness probes due to `HTTP 500` on `/healthz`.

## Likely Root Cause
Ingress is returning HTTP 502/503 because `api-service` has 0 ready endpoints due to failing readiness probes on backing pods.

## Confidence Level
**High**

## Recommended Remediation
Inspect application database connection pools causing `/healthz` 500 errors or temporarily adjust readiness probe thresholds.

## Human Approval Required
Human approval required before applying deployment manifest changes:

```bash
kubectl rollout restart deployment/api-deployment --namespace production
```
```
