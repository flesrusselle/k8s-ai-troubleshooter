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
helm status <release-name> -n <namespace>

# 3. View revision history
helm history <release-name> -n <namespace>
```

## Detailed Investigation

1. **Check Release Status**:
   - `failed`: Rendered manifests applied but resources failed health checks or hooks failed.
   - `pending-upgrade`: Previous helm upgrade process was killed mid-execution, leaving secret lock active.
2. **Inspect Deployed User Values**:
   ```bash
   helm get values <release-name> -n <namespace>
   ```
3. **Inspect Rendered Manifests**:
   ```bash
   helm get manifest <release-name> -n <namespace>
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

## Human Approval Required
- `helm rollback <release-name> <revision-number> -n <namespace>` (**HUMAN APPROVAL REQUIRED**)
- `helm uninstall <release-name> -n <namespace>` (**DESTRUCTIVE — HUMAN APPROVAL REQUIRED**)

## Related Runbooks
- [helm-ownership.md](file:///Users/flestorres/Desktop/apply/k8s-ai-troubleshooter/runbooks/helm/helm-ownership.md)
- [deployment-stuck.md](file:///Users/flestorres/Desktop/apply/k8s-ai-troubleshooter/runbooks/deployments/deployment-stuck.md)

## Official Documentation
- [Helm Architecture and Troubleshooting](https://helm.sh/docs/topics/architecture/)
