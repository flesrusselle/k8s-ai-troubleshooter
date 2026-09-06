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
kubectl get deployment <deployment-name> --namespace <namespace> -o jsonpath='{.metadata.labels.app\.kubernetes\.io/managed-by}'

# 2. Check Helm release name annotation
kubectl get deployment <deployment-name> --namespace <namespace> -o jsonpath='{.metadata.annotations.meta\.helm\.sh/release-name}'
```

## Detailed Investigation

1. **Verify Managed-By Label**:
   Standard Helm releases inject `app.kubernetes.io/managed-by: Helm`.
2. **Retrieve Helm Release Information**:
   ```bash
   helm status <release-name> --namespace <namespace>
   helm get values <release-name> --namespace <namespace>
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

## Blast Radius
Editing ownership annotations changes which release manages a resource. Get it
wrong and two releases believe they own one object, or none does — the second
case leaves the resource orphaned and unmanaged by any subsequent upgrade.

## Human Approval Required
- `helm upgrade <release-name> <chart> -f values.yaml` (**HUMAN APPROVAL REQUIRED**)

## Verification
```bash
kubectl get <resource> <name> --namespace <namespace> \
  -o jsonpath='{.metadata.annotations.meta\.helm\.sh/release-name}{"\n"}'
helm upgrade --dry-run <release> <chart> --namespace <namespace>
```
Verified when the annotation names the intended release and a dry-run upgrade
completes without an ownership error. Use the dry run — it is the whole point of
having one.

## Rollback
Restore the previous annotation values. A resource adopted into the wrong
release will be modified or deleted by that release's next operation, so correct
ownership before running any further Helm command.

## Related Runbooks
- [helm-troubleshooting.md](helm-troubleshooting.md)

## Official Documentation
- [Helm Annotations and Labels](https://helm.sh/docs/chart_best_practices/labels_and_annotations/)
