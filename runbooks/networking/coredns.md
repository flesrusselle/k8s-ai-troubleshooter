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
kubectl get pods -n kube-system -l k8s-app=kube-dns -o wide

# 2. Check CoreDNS Service and Endpoint status
kubectl get svc,endpoints -n kube-system -l k8s-app=kube-dns

# 3. Fetch CoreDNS container logs
kubectl logs -n kube-system -l k8s-app=kube-dns --tail=100
```

## Detailed Investigation

Follow the deterministic CoreDNS diagnostic path:

```text
DNS Resolution Failure
       ↓
Check CoreDNS Pod Status (`kubectl get pods -n kube-system -l k8s-app=kube-dns`)
       ↓
Check kube-dns Service & Endpoints (`kubectl get endpoints -n kube-system`)
       ↓
Check CoreDNS Logs (`kubectl logs -n kube-system -l k8s-app=kube-dns`)
       ↓
Check CoreDNS ConfigMap (`kubectl get configmap coredns -n kube-system -o yaml`)
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

## Human Approval Required
- `kubectl rollout restart deployment coredns -n kube-system` (**HUMAN APPROVAL REQUIRED**)

## Related Runbooks
- [endpoints.md](file:///Users/flestorres/Desktop/apply/k8s-ai-troubleshooter/runbooks/networking/endpoints.md)

## Official Documentation
- [Debugging DNS Resolution](https://kubernetes.io/docs/tasks/administer-cluster/dns-debugging-resolution/)
