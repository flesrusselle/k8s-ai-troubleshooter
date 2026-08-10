# Admission Webhook Failure Runbook

## Purpose
Diagnose failures where the API server rejects or cannot complete a request
because an admission webhook denied it, timed out, or is unreachable.

## When to Use
Any error containing `failed calling webhook`, `admission webhook ... denied the
request`, or `context deadline exceeded` on a create or update — especially when
*every* deploy to a namespace suddenly fails.

## Safety Level
`SAFE_READ`

## Symptoms
- `Error from server (InternalError): failed calling webhook "x.y.z": ... connection refused`.
- `admission webhook "validate.x.y" denied the request: <reason>`.
- All creates in a namespace fail while existing workloads keep running.
- `kubectl apply` hangs for ~30 seconds then fails with a timeout.
- A cluster upgrade or cert rotation immediately preceded the failure.

## Quick Diagnosis

```bash
# 1. Which webhooks exist, and what do they intercept?
kubectl get validatingwebhookconfigurations
kubectl get mutatingwebhookconfigurations

# 2. The failure policy is the critical field
kubectl get validatingwebhookconfigurations <name> \
  -o jsonpath='{range .webhooks[*]}{.name}{"\t"}{.failurePolicy}{"\t"}{.clientConfig.service.namespace}/{.clientConfig.service.name}{"\n"}{end}'

# 3. Is the backing service alive?
kubectl get pods -n <webhook-namespace>
kubectl get endpoints -n <webhook-namespace> <webhook-service>

# 4. The webhook pod's own logs
kubectl logs -n <webhook-namespace> -l <webhook-selector> --tail=100
```

## Detailed Investigation

```text
failed calling webhook
       ↓
Is this a denial or an outage?
       ↓
"denied the request: <reason>"  → the webhook worked; your object violates policy
"connection refused" / "no endpoints" / "context deadline exceeded"
                                → the webhook is down
       ↓ (down)
Does the webhook service have endpoints?
       ↓ no  → the webhook's own pods are not running
       ↓ yes
Is the CA bundle still valid?
       ↓ no  → certificate rotated without updating caBundle
       ↓ yes
Does a NetworkPolicy block the API server from reaching it?
```

1. **Distinguish denial from outage first.** A denial is the system working: read
   the reason and fix the object. An outage means the webhook cannot be reached,
   and the blast radius depends entirely on `failurePolicy`.
2. **`failurePolicy: Fail` turns a webhook outage into a cluster outage** for
   every resource it intercepts. This is why "nothing can deploy" so often traces
   to one crashed pod in a policy namespace.
3. **Self-referential deadlock is common.** If a webhook intercepts pods in *all*
   namespaces including its own, and all its pods are down, it cannot be
   rescheduled — creating its replacement pod requires the webhook to admit it.
   Check for `namespaceSelector` exclusions on the webhook's own namespace.
4. **Certificate expiry is a scheduled outage.** Webhooks are served over TLS and
   the `caBundle` must match. Rotation without updating the configuration breaks
   every intercepted request at once, with no deploy to correlate it to.

## Decision Tree
Self-contained; branch on denial versus outage as above.

## Evidence to Collect
- Full error text, including the webhook name and namespace.
- `failurePolicy`, `timeoutSeconds`, `namespaceSelector` and `rules` for that webhook.
- Whether the backing Service has endpoints.
- The webhook pod's logs and restart count.
- Certificate expiry on the webhook's serving secret.
- Time of first failure versus any cluster upgrade or cert rotation.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| `connection refused`, service has no endpoints | Webhook pods are down or unschedulable | High |
| `x509: certificate has expired` | Serving cert expired; `caBundle` stale | High |
| `context deadline exceeded` | Webhook slower than `timeoutSeconds`, often under load | High |
| `denied the request: <policy reason>` | Working as designed — the object violates policy | High |
| Everything broke with no deploy, at a round time | Certificate expiry | Medium |
| Webhook cannot be rescheduled after eviction | Self-referential deadlock; needs `namespaceSelector` exclusion | Medium |
| Only one namespace affected | `namespaceSelector` scopes it there | High |

## Confirmation
Confirm reachability from inside the cluster:

```bash
kubectl get endpoints -n <webhook-namespace> <webhook-service>
```

Empty endpoints with `failurePolicy: Fail` is a complete explanation for
cluster-wide create failures. If endpoints exist and the error persists, suspect
TLS: compare the `caBundle` in the webhook configuration against the CA of the
certificate the service is actually serving.

## Remediation
Restore the webhook's pods, renew and re-publish its certificate, or raise
`timeoutSeconds`. In a genuine emergency the webhook configuration can be
deleted to unblock the cluster — this disables the policy it enforces, so treat
it as an incident action with an explicit follow-up to restore it.

## Human Approval Required
- `kubectl apply -f <webhook-configuration>.yaml`
- `kubectl rollout restart deployment/<webhook> -n <webhook-namespace>`
- `kubectl delete validatingwebhookconfiguration <name>` — **DESTRUCTIVE**, disables policy enforcement cluster-wide

## Related Runbooks
- [rbac-forbidden.md](rbac-forbidden.md)
- [pod-security-admission.md](pod-security-admission.md)
- [../cluster/certificate-expiry.md](../cluster/certificate-expiry.md)
- [../deployments/deployment-stuck.md](../deployments/deployment-stuck.md)

## Official Documentation
- [Dynamic Admission Control](https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/)
- [Admission Controllers Reference](https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/)
