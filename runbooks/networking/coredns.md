# CoreDNS Troubleshooting Runbook

## Purpose
Diagnose cluster-wide internal DNS resolution failures caused by CoreDNS pod or service issues.

## When to Use
Triggered when workloads fail to resolve internal `.cluster.local` domain names or external DNS queries timeout (`Could not resolve host`).

## Safety Level
`SAFE_READ`

## Symptoms
- Applications log `DNS resolution failed` or `Name or service not known`.
- `nslookup kubernetes.default` fails inside pod.

## Quick Diagnosis

```bash
# 1. Check CoreDNS pod status in kube-system
kubectl get pods --namespace kube-system -l k8s-app=kube-dns -o wide

# 2. Check CoreDNS Service and Endpoint status
kubectl get svc,endpoints --namespace kube-system -l k8s-app=kube-dns

# 3. Fetch CoreDNS container logs
kubectl logs --namespace kube-system -l k8s-app=kube-dns --tail=100
```

## Detailed Investigation

Follow the deterministic CoreDNS diagnostic path:

```text
DNS Resolution Failure
       ↓
Check CoreDNS Pod Status (`kubectl get pods --namespace kube-system -l k8s-app=kube-dns`)
       ↓
Check kube-dns Service & Endpoints (`kubectl get endpoints --namespace kube-system`)
       ↓
Check CoreDNS Logs (`kubectl logs --namespace kube-system -l k8s-app=kube-dns`)
       ↓
Check CoreDNS ConfigMap (`kubectl get configmap coredns --namespace kube-system -o yaml`)
       ↓
Test DNS from disposable diagnostic environment
```

1. **Verify CoreDNS Pod States**: Ensure CoreDNS replicas are `Running` and ready.
2. **Inspect Endpoints**: Verify `kube-dns` service points to active CoreDNS pod IPs.
3. **Inspect CoreDNS Logs**: Look for upstream forward loop errors or plugin panics.

## Decision Tree
`decision-trees/networking.yaml`

## Evidence to Collect
- CoreDNS pod phases and restart counts.
- `kube-dns` endpoint IPs.
- CoreDNS log output for plugin errors or upstream timeout.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| `CoreDNS loop detected` | Upstream resolver loop in `/etc/resolv.conf` | High |
| `kube-dns` endpoints empty | CoreDNS readiness probe failing or selector mismatch | High |
| `i/o timeout` to upstream DNS | Cloud VPC security group blocking outbound UDP port 53 | High |

## Confirmation
Confirm DNS functionality using a safe diagnostic lookup test.

## Remediation
Fix upstream `/etc/resolv.conf` forwarding loop or adjust CoreDNS ConfigMap.

## Blast Radius
CoreDNS serves the entire cluster. Restarting it, editing its ConfigMap, or
scaling it affects name resolution for every pod — including ones that are
currently healthy. Treat any CoreDNS change as cluster-wide.

## Human Approval Required
- `kubectl rollout restart deployment coredns --namespace kube-system` (**HUMAN APPROVAL REQUIRED**)

## Verification
```bash
kubectl run dnscheck --rm -it --restart=Never --image=busybox:1.36 --namespace <namespace> \
  -- nslookup kubernetes.default.svc.cluster.local
```
Verified when resolution succeeds from a pod in the affected namespace, not just
from the CoreDNS pod itself. Test both a cluster name and an external name — they
take different paths through the Corefile.

## Rollback
Restore the previous CoreDNS ConfigMap and restart the deployment. A malformed
Corefile will crash-loop CoreDNS and take cluster DNS down entirely, so keep a
copy of the working ConfigMap before editing it.

## Related Runbooks
- [endpoints.md](endpoints.md)

## Official Documentation
- [Debugging DNS Resolution](https://kubernetes.io/docs/tasks/administer-cluster/dns-debugging-resolution/)
