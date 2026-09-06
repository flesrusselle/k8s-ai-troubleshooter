# Helm Release Failure & Rollback Runbook

## Purpose
Diagnose failed, stuck, or inconsistent Helm releases (`failed`, `pending-upgrade`, `pending-rollback`).

## When to Use
Triggered when `helm upgrade` or `helm install` fails, or a Helm release status is non-deployed.

## Safety Level
`SAFE_READ`

## Symptoms
- Helm release status: `failed` or `pending-upgrade`.
- Helm error: `another operation is in progress` or `upgrade failed: timed out waiting for the condition`.

## Quick Diagnosis

```bash
# 1. List release status and revision across namespaces
helm list -A

# 2. Inspect detailed status of affected release
helm status <release-name> --namespace <namespace>

# 3. View revision history
helm history <release-name> --namespace <namespace>
```

## Detailed Investigation

1. **Check Release Status**:
   - `failed`: Rendered manifests applied but resources failed health checks or hooks failed.
   - `pending-upgrade`: Previous helm upgrade process was killed mid-execution, leaving secret lock active.
2. **Inspect Deployed User Values**:
   ```bash
   helm get values <release-name> --namespace <namespace>
   ```
3. **Inspect Rendered Manifests**:
   ```bash
   helm get manifest <release-name> --namespace <namespace>
   ```

## Decision Tree
`decision-trees/helm.yaml`

## Evidence to Collect
- Helm release status and revision list.
- User values YAML.
- Helm status notes & failure output.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| `timed out waiting for condition` | Subordinate deployment pods failed readiness probe during helm wait | High |
| `another operation in progress` | Previous CI/CD job aborted abruptly leaving secret lock | High |

## Confirmation
Confirm whether underlying Kubernetes workload resources failed or Helm chart hook failed.

## Remediation
Roll back release to last stable revision or clear release lock.

## Blast Radius
`helm upgrade` can replace, recreate or delete resources depending on the
chart's diff — including PersistentVolumeClaims in some charts. `helm rollback`
carries the same risk in reverse. Review the diff before either.

## Human Approval Required
- `helm rollback <release-name> <revision-number> --namespace <namespace>` (**HUMAN APPROVAL REQUIRED**)
- `helm uninstall <release-name> --namespace <namespace>` (**DESTRUCTIVE — HUMAN APPROVAL REQUIRED**)

## Verification
```bash
helm status <release> --namespace <namespace>
helm history <release> --namespace <namespace>
kubectl get pods --namespace <namespace>
```
Verified when `helm status` reports `deployed`, the newest revision is the one
you intended, and the underlying pods are healthy. A `deployed` release with
failing pods means Helm succeeded and the workload did not.

## Rollback
`helm rollback <release> <revision> --namespace <namespace>` returns the previous
manifest as a new revision. It does not restore data deleted by the failed
upgrade, and it cannot recover a release whose history was pruned by
`--history-max`.

## Related Runbooks
- [helm-ownership.md](helm-ownership.md)
- [deployment-stuck.md](../deployments/deployment-stuck.md)

## Official Documentation
- [Helm Architecture and Troubleshooting](https://helm.sh/docs/topics/architecture/)
