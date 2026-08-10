# NetworkPolicy Packet Drop Runbook

## Purpose
Diagnose inter-pod or pod-to-external network connection timeouts caused by restrictive NetworkPolicy rules or CNI enforcement.

## When to Use
Triggered when pods can resolve DNS but cannot establish TCP/UDP socket connections to backend services or databases.

## Safety Level
`SAFE_READ`

## Symptoms
- TCP connection timeout (`ETIMEDOUT`).
- Pod cannot connect to database in another namespace.

## Quick Diagnosis

```bash
# 1. List active NetworkPolicies in namespace
kubectl get networkpolicies -n <namespace>

# 2. Inspect ingress/egress spec rules for policy
kubectl get networkpolicy <policy-name> -n <namespace> -o yaml
```

## Detailed Investigation

1. **Check Ingress & Egress Selectors**:
   Verify if `podSelector`, `namespaceSelector`, or `ipBlock` in NetworkPolicy covers source and destination pods.
2. **Verify Default Deny Policies**:
   Check if a `default-deny-all` NetworkPolicy is deployed in the namespace.

## Decision Tree
`decision-trees/networking.yaml`

## Evidence to Collect
- Active NetworkPolicies in source and destination namespaces.
- Source and destination pod labels.
- CNI plugin type (Calico, Cilium, Weave).

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| Connection timeout + default-deny policy | Missing explicit egress/ingress rule for target port | High |
| Cross-namespace timeout | `namespaceSelector` label missing on target namespace | High |

## Confirmation
Verify rule matching by inspecting NetworkPolicy YAML specs against pod and namespace labels.

## Remediation
Apply updated NetworkPolicy rule allowing target port traffic.

## Human Approval Required
- `kubectl apply -f networkpolicy.yaml` (**HUMAN APPROVAL REQUIRED**)

## Related Runbooks
- [coredns.md](coredns.md)

## Official Documentation
- [Kubernetes Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
