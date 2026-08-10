# Helm Release Ownership Discovery Runbook

## Purpose
Determine whether an unhealthy Kubernetes workload or resource is managed by a Helm release, identifying the release name, chart version, and values.

## When to Use
Triggered whenever investigating a failing `Deployment`, `StatefulSet`, `DaemonSet`, `Service`, `ConfigMap`, or `Ingress` to check if direct manifest changes will be overwritten by Helm.

## Safety Level
`SAFE_READ`

## Symptoms
- Need to know if direct `kubectl edit/patch` will be overwritten by Helm automation.
- Need to trace resource parameters back to Helm `values.yaml`.

## Quick Diagnosis

```bash
# 1. Check Helm manager label on Kubernetes workload
kubectl get deployment <deployment-name> -n <namespace> -o jsonpath='{.metadata.labels.app\.kubernetes\.io/managed-by}'

# 2. Check Helm release name annotation
kubectl get deployment <deployment-name> -n <namespace> -o jsonpath='{.metadata.annotations.meta\.helm\.sh/release-name}'
```

## Detailed Investigation

1. **Verify Managed-By Label**:
   Standard Helm releases inject `app.kubernetes.io/managed-by: Helm`.
2. **Retrieve Helm Release Information**:
   ```bash
   helm status <release-name> -n <namespace>
   helm get values <release-name> -n <namespace>
   ```

## Decision Tree
`decision-trees/helm.yaml`

## Evidence to Collect
- `managed-by` label value.
- `meta.helm.sh/release-name` annotation value.
- Helm release chart version and user values.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| `managed-by: Helm` + release found | Resource is fully managed by Helm; remediation must update Helm values | High |
| No Helm annotations | Resource deployed via plain manifests, Kustomize, or GitOps operator | High |

## Confirmation
Confirm resource ownership via annotations and `helm list` cross-reference.

## Remediation
Update parameters in Helm `values.yaml` rather than editing live Kubernetes objects.

## Human Approval Required
- `helm upgrade <release-name> <chart> -f values.yaml` (**HUMAN APPROVAL REQUIRED**)

## Related Runbooks
- [helm-troubleshooting.md](helm-troubleshooting.md)

## Official Documentation
- [Helm Annotations and Labels](https://helm.sh/docs/chart_best_practices/labels_and_annotations/)
