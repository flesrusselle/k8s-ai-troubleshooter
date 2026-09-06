# LoadBalancer Pending Runbook

## Purpose
Diagnose Services of type `LoadBalancer` whose `EXTERNAL-IP` never leaves
`<pending>`.

## When to Use
`kubectl get svc` shows `<pending>` under `EXTERNAL-IP` for longer than a few
minutes.

## Safety Level
`SAFE_READ`

## Symptoms
- `EXTERNAL-IP` stuck at `<pending>` indefinitely.
- No events on the Service, or repeated `SyncLoadBalancerFailed`.
- Works in a managed cluster, never provisions on bare metal or kind.
- Provisioning succeeded last month and fails now.

## Quick Diagnosis

```bash
# 1. The events say why, when there is a controller to say it
kubectl describe service <name> --namespace <namespace>

# 2. Is there a controller to provision it at all?
kubectl get pods -A | grep -Ei 'cloud-controller|metallb|kube-vip|nginx-ingress'

# 3. Cloud controller manager logs, if present
kubectl logs --namespace kube-system -l component=cloud-controller-manager --tail=100

# 4. The Service spec, including any provider annotations
kubectl get service <name> --namespace <namespace> -o yaml
```

## Detailed Investigation

```text
EXTERNAL-IP <pending>
       ↓
Is a load balancer controller running?
       ↓ no  → nothing will ever provision it
       │        bare metal / kind / minikube without MetalLB
       ↓ yes
Any events on the Service?
       ↓ no  → the controller is not reconciling this Service at all
       ↓ yes
"SyncLoadBalancerFailed" → read the provider error:
       quota exceeded / subnet not tagged / permission denied /
       no free address in pool
```

1. **`LoadBalancer` requires something outside Kubernetes to implement it.** In a
   managed cluster that is the cloud controller manager. On bare metal, kind, or
   minikube there is nothing by default, and the Service will stay `<pending>`
   forever with no error — because no component ever claimed it.
2. **No events at all is diagnostic.** It means no controller is even attempting
   the work. Events showing failures mean a controller exists and is being
   refused, which is a different and much more actionable problem.
3. **Cloud quota and subnet tagging are the usual managed-cluster causes.** Load
   balancer count quotas are low by default, and public subnets typically must
   carry a provider-specific tag before they are eligible.
4. **Provider annotations are not portable.** Annotations for internal load
   balancers, health check paths, and SSL certificates are provider-specific; a
   manifest that provisioned on one cloud may be silently ignored on another.
5. **`externalTrafficPolicy: Local` changes health checking**, not provisioning.
   It can make a provisioned load balancer route to only some nodes, which
   presents as a partial outage rather than as `<pending>`.

## Decision Tree
`decision-trees/networking.yaml`

## Evidence to Collect
- Events on the Service, or their absence.
- Whether a cloud controller manager or MetalLB is running.
- Cluster type: managed, bare metal, or local development.
- Provider-specific annotations on the Service.
- Cloud-side load balancer quota and subnet tagging.
- MetalLB `IPAddressPool` and remaining free addresses, where applicable.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| No events at all, local cluster | No load balancer implementation installed | High |
| `SyncLoadBalancerFailed: quota exceeded` | Cloud load balancer quota reached | High |
| `could not find any suitable subnets` | Subnets missing the provider's required tag | High |
| `AccessDenied` / `Forbidden` in controller logs | Cluster IAM role lacks load balancer permissions | High |
| MetalLB installed, still pending | Address pool exhausted or not configured | High |
| Provisioned before, pending now | Quota consumed by other Services, or the cloud role changed | Medium |
| IP assigned but unreachable | Provisioning succeeded — this is a routing problem, not this runbook | High |

## Confirmation
Confirm the missing-implementation hypothesis by checking whether any controller
is watching Services:

```bash
kubectl get events --namespace <namespace> --field-selector involvedObject.name=<service>
```

An empty event list for a `LoadBalancer` Service that has existed for minutes
confirms that nothing is attempting to provision it — install MetalLB or an
equivalent, or use `NodePort` instead.

## Remediation
Install a load balancer implementation for bare-metal clusters, raise the cloud
quota, tag the subnets, grant the missing IAM permissions, or expand the MetalLB
address pool. For local development, `NodePort` or `kubectl port-forward` avoids
the dependency entirely.

## Blast Radius
Provisioning a load balancer creates a billable cloud resource and usually a
public endpoint. Switching a Service to `NodePort` changes how it is exposed and
may bypass controls attached to the load balancer.

## Human Approval Required
- `kubectl apply -f <metallb-config>.yaml`
- `kubectl patch service <name> --namespace <ns> -p '{"spec":{"type":"NodePort"}}'` — changes how the Service is exposed
- Cloud-side quota or IAM changes — outside the cluster, and outside this project's scope

## Verification
```bash
kubectl get service <service> --namespace <namespace>
```
Verified when `EXTERNAL-IP` shows an address and traffic reaches the backend from
outside the cluster. An assigned IP proves provisioning succeeded, not that
routing works — test the path end-to-end.

## Rollback
Reverting the Service type releases the load balancer, which usually releases
its public IP permanently. If that address was in DNS or an allowlist, plan for
it not coming back.

## Related Runbooks
- [ingress.md](ingress.md)
- [service-unreachable.md](service-unreachable.md)
- [endpoints.md](endpoints.md)
- [../cluster/cluster-health.md](../cluster/cluster-health.md)

## Official Documentation
- [Service Type LoadBalancer](https://kubernetes.io/docs/concepts/services-networking/service/#loadbalancer)
- [Cloud Controller Manager](https://kubernetes.io/docs/concepts/architecture/cloud-controller/)
