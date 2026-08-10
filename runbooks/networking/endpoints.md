# Service Endpoints & Selector Mismatch Runbook

## Purpose
Diagnose Kubernetes Services failing to route traffic to pods due to endpoint binding failure or label selector mismatch.

## When to Use
Triggered when a Service is reachable but returns `503 Service Unavailable`, `Connection refused`, or has empty endpoints.

## Safety Level
`SAFE_READ`

## Symptoms
- `kubectl get endpoints <service-name>` shows `<none>`.
- Client requests to ClusterIP return connection errors.

## Quick Diagnosis

```bash
# 1. Fetch Service selector configuration
kubectl get svc <service-name> -n <namespace> -o jsonpath='{.spec.selector}'

# 2. Compare with actual backing Pod labels
kubectl get pods -n <namespace> --show-labels

# 3. Check Endpoint / EndpointSlice status
kubectl get endpoints,endpointslices -n <namespace> -l kubernetes.io/service-name=<service-name>
```

## Detailed Investigation

Compare Service selector against Pod labels:

```text
Service Selector:  app=api, env=prod
        vs
Pod Labels:        app=api, env=production   <-- MISMATCH (`prod` vs `production`)
```

1. **Verify Label Selector**: Ensure key-value pairs match exactly.
2. **Verify Pod Readiness**: Ensure backing pods are passing readiness probes. Unready pods are excluded from Endpoints.
3. **Verify Port Mapping**: Check `spec.ports[*].targetPort` matches the container's listening port.

## Decision Tree
`decision-trees/networking.yaml`

## Evidence to Collect
- Service `spec.selector` JSON output.
- Backing Pod labels.
- Endpoint slice list.
- Pod readiness probe status.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| Endpoints `<none>` + pods unready | Backing pods failing readiness probes | High |
| Endpoints `<none>` + pods running | Label selector typo in Service spec | High |
| Connection refused on Pod IP | Container listening on different targetPort | High |

## Confirmation
Match Pod labels with Service selector key/value map.

## Remediation
Update Service selector or fix pod readiness probes.

## Human Approval Required
- `kubectl patch svc <service-name> -n <namespace> -p '...'`

## Related Runbooks
- [probes.md](../pods/probes.md)
- [ingress.md](ingress.md)

## Official Documentation
- [Services and Endpoints](https://kubernetes.io/docs/concepts/services-networking/service/)
