# Service Unreachable Runbook

## Purpose
Diagnose pod-to-service connectivity failures within the cluster, isolating
which of the four hops between caller and workload is broken.

## When to Use
A pod cannot reach another pod through a Service — connection refused, timeouts,
or intermittent failures — and DNS has already been ruled out.

## Safety Level
`SAFE_READ`

## Symptoms
- `connection refused` or `i/o timeout` calling an in-cluster Service.
- `curl` to the Service IP fails but the pod IP works.
- Intermittent failures — roughly a fixed fraction of requests.
- Works from one namespace, not another.

## Quick Diagnosis

Connectivity has four hops. Test them in order; the first failure localises the
fault and the remaining checks become unnecessary.

```bash
# Hop 1 — does the Service resolve?
kubectl run netcheck --rm -it --restart=Never --image=busybox:1.36 --namespace <namespace> \
  -- nslookup <service>.<namespace>.svc.cluster.local

# Hop 2 — does the Service have endpoints?
kubectl get endpoints <service> --namespace <namespace>

# Hop 3 — are the endpoint pods ready?
kubectl get pods --namespace <namespace> -l <service-selector> -o wide

# Hop 4 — is anything listening on the target port?
kubectl get service <service> --namespace <namespace> \
  -o jsonpath='{.spec.ports[*].targetPort}{"\n"}'
```

## Detailed Investigation

```text
Service unreachable
       ↓
Hop 1: DNS resolves?
       ↓ no  → coredns.md
       ↓ yes
Hop 2: Endpoints present?
       ↓ no  → endpoints.md — selector matches nothing, or no pod is Ready
       ↓ yes
Hop 3: Endpoint pods Ready?
       ↓ no  → probes.md — unready pods are removed from endpoints
       ↓ yes
Hop 4: targetPort matches containerPort?
       ↓ no  → traffic is delivered to a port nothing listens on
       ↓ yes
NetworkPolicy dropping it? → network-policy.md
```

1. **`ENDPOINTS <none>` is the highest-value single observation.** It means the
   Service selects no ready pod, and it distinguishes a routing problem from an
   application problem immediately.
2. **Readiness gates traffic.** A pod that is Running but not Ready is removed
   from the Service's endpoints. "The pod is up but the Service is down" is
   usually this, and belongs to the probes runbook.
3. **Intermittent failure across N replicas means one bad backend.** If roughly
   one request in three fails with three replicas, one endpoint is broken while
   the Service keeps load balancing to it — it is Ready but not healthy.
4. **`port` and `targetPort` are different things.** `port` is what callers dial;
   `targetPort` is the container port traffic is forwarded to. A mismatch
   produces `connection refused` from a Service that looks perfectly configured.
5. **Headless Services have no cluster IP.** `clusterIP: None` returns pod IPs
   directly from DNS; client-side behaviour differs and there is no kube-proxy
   load balancing to blame.

## Decision Tree
`decision-trees/networking.yaml`

## Evidence to Collect
- `kubectl get endpoints <service>` — present, empty, or partially populated.
- The Service's `selector` and the pods' actual labels, compared literally.
- `port`, `targetPort`, `protocol`, and the container's `containerPort`.
- Readiness state of every backing pod.
- NetworkPolicies in the namespace, and whether a default-deny exists.
- Whether failures are total or fractional.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| `ENDPOINTS <none>`, pods running | Selector does not match pod labels | High |
| `ENDPOINTS <none>`, pods not Ready | Readiness probe failing; pods excluded from routing | High |
| Pod IP works, Service IP does not | `targetPort` mismatch, or kube-proxy unhealthy on that node | High |
| Fraction of requests fail | One endpoint Ready but broken | High |
| Works in-namespace, fails cross-namespace | NetworkPolicy, or short name used instead of FQDN | High |
| Connection refused immediately | Nothing listening on `targetPort` | High |
| Timeout rather than refusal | Packets dropped — NetworkPolicy or CNI | Medium |

## Confirmation
Confirm the selector hypothesis by comparing what the Service asks for against
what the pods carry:

```bash
kubectl get service <service> --namespace <namespace> -o jsonpath='{.spec.selector}{"\n"}'
kubectl get pods --namespace <namespace> --show-labels
```

A selector key absent from the pod labels — or differing in case — fully explains
empty endpoints, and no further network investigation is warranted.

## Remediation
Correct the Service selector or the pod labels so they match, fix `targetPort`
to match `containerPort`, repair the readiness probe so healthy pods are
admitted to the endpoint set, or amend the NetworkPolicy that is dropping the
traffic.

## Blast Radius
Depends on the hop repaired. Selector and label changes re-route live traffic;
`targetPort` changes affect every caller of the Service; readiness probe changes
affect which pods receive traffic across the whole workload.

## Human Approval Required
- `kubectl apply -f <corrected-service>.yaml`
- `kubectl label pod <pod> <key>=<value> --namespace <namespace>`
- `kubectl rollout restart deployment/<name> --namespace <namespace>`

## Verification
```bash
kubectl get endpoints <service> --namespace <namespace>
kubectl run netcheck --rm -it --restart=Never --image=busybox:1.36 --namespace <namespace> \
  -- wget -qO- --timeout=5 http://<service>.<namespace>.svc.cluster.local
```
Verified when the request succeeds repeatedly. Repetition matters: with several
backends, a single success can hit a healthy endpoint while a broken one remains
in rotation. Send at least as many requests as there are endpoints.

## Rollback
Restore the previous Service definition or pod labels. If traffic was
temporarily routed to an unintended backend, any writes it accepted persist.

## Related Runbooks
- [endpoints.md](endpoints.md)
- [coredns.md](coredns.md)
- [network-policy.md](network-policy.md)
- [../pods/probes.md](../pods/probes.md)

## Official Documentation
- [Service](https://kubernetes.io/docs/concepts/services-networking/service/)
- [Debug Services](https://kubernetes.io/docs/tasks/debug/debug-application/debug-service/)
