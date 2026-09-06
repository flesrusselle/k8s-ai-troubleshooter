# ArgoCD Sync Failure Runbook

## Purpose
Diagnose an ArgoCD `Application` that will not reach `Synced`/`Healthy`, or
that reports `Synced` while the workload it manages is not actually working.

## When to Use
`kubectl get applications.argoproj.io --namespace argocd` shows anything other than
`Synced` + `Healthy`, or a deploy that "went through in Git" never appears in
the cluster.

## Safety Level
`SAFE_READ`

## Symptoms
- Sync status `OutOfSync` that never clears, even after a manual sync.
- Sync status `Unknown`, or a `ComparisonError` condition.
- Operation phase `Failed` or `Error` with a message from a sync hook.
- Sync status `Synced`, health status `Degraded` — the manifests applied, but
  the resource they created is unhealthy.

## Quick Diagnosis

Sync status and health status are two different axes, and reading them
together is most of the diagnosis:

```bash
# 1. The two axes, side by side
kubectl get application <app> --namespace argocd \
  -o jsonpath='{.status.sync.status}{"\t"}{.status.health.status}{"\n"}'

# 2. Why comparison or sync failed, in ArgoCD's own words
kubectl get application <app> --namespace argocd \
  -o jsonpath='{range .status.conditions[*]}{.type}{": "}{.message}{"\n"}{end}'

# 3. The last sync operation's own report
kubectl get application <app> --namespace argocd \
  -o jsonpath='{.status.operationState.phase}{"\t"}{.status.operationState.message}{"\n"}'

# 4. The controllers that actually do the work
kubectl logs --namespace argocd deployment/argocd-application-controller --tail=100
kubectl logs --namespace argocd deployment/argocd-repo-server --tail=100
```

## Detailed Investigation

```text
Application not Synced+Healthy
       ↓
Read sync status AND health status — they are independent
       ↓
Sync: OutOfSync, Health: Healthy
       → live state differs from Git, but what's running still works.
         Often a controller-owned field (HPA replicas, a mutating webhook
         default) diffing on every reconcile — see ignoreDifferences below.
       ↓
Sync: Synced, Health: Degraded
       → manifests were applied correctly; the resource they created is
         broken. This is not an ArgoCD problem — route the underlying
         resource (Deployment, Pod) through symptom-index.yaml as normal.
       ↓
Sync: Unknown / ComparisonError
       → repo-server could not render or diff the manifests: a missing CRD,
         a broken chart, or the repo-server itself unreachable.
       ↓
operationState.phase: Failed, message names a hook
       → a PreSync/Sync/PostSync Job failed — read that Job's own pods
         (runbooks/workloads/job-failures.md), not the Application.
```

1. **Sync and health are orthogonal.** Sync asks "does the live state match
   Git?" Health asks "is that state actually working?" A `Synced` +
   `Degraded` application is functioning exactly as instructed — the fault is
   in what Git says to deploy, not in ArgoCD.
2. **Perpetual `OutOfSync` is usually a live field, not a real drift.** A
   Deployment's `.spec.replicas` written by an HPA, or a default a mutating
   webhook injects, will differ from Git on every single comparison. The fix
   is `spec.ignoreDifferences` on the Application, not repeated manual syncs.
3. **`ComparisonError` naming a CRD often means ordering, not a missing
   manifest.** An "app of apps" that installs a CRD and a custom resource of
   that type in the same wave can have the custom resource compared before
   the CRD exists. Sync waves or a separate Application for CRDs fixes this.
4. **Health status for a custom CRD can read `Unknown` while the resource is
   fine.** ArgoCD's health check for unrecognized CRDs is `Unknown` unless a
   Lua health check is registered for that resource kind. `Unknown` is not
   evidence of a problem by itself — check the resource's own status.
5. **Self-heal reverts manual `kubectl` changes.** If `syncPolicy.automated.selfHeal`
   is enabled, a direct edit made against the live cluster will be reverted at
   the next reconcile. That is by design, not a bug — the fix belongs in Git.

## Decision Tree
Route the underlying resource through `symptom-index.yaml` once sync status is
`Synced` and only health is failing; this runbook's own steps otherwise.

## Evidence to Collect
- `sync.status`, `health.status`, and every entry in `status.conditions`.
- `operationState.phase` and `.message` from the last sync attempt.
- Whether `syncPolicy.automated` and `selfHeal` are enabled.
- `spec.ignoreDifferences`, if any, and whether the diffing field is covered.
- `argocd-repo-server` logs, for rendering/comparison errors.
- Whether the target namespace/cluster's RBAC actually grants ArgoCD's
  ServiceAccount the verbs the manifest needs.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| `OutOfSync` forever, no error, one field diffing | Controller-owned field not in `ignoreDifferences` | High |
| `Synced`, health `Degraded` | The workload itself is unhealthy — not an ArgoCD fault | High |
| `ComparisonError` naming a CRD | CRD not yet installed, or a sync-wave ordering issue | High |
| Operation `Failed`, message names a Job | A sync hook failed — read the Job's pods | High |
| `Forbidden`/`is forbidden` in operation message | ArgoCD's ServiceAccount lacks RBAC in the target namespace | High |
| repo-server error: path/chart not found | Broken reference in the source repo | High |
| Manual `kubectl` edit reverted shortly after | `selfHeal: true` — working as designed | High |
| Health `Unknown` on a custom resource | No health check registered for that CRD kind | Medium |

## Confirmation
Confirm a live-field-diff hypothesis by diffing the specific field ArgoCD
reports as different against what actually manages it:

```bash
kubectl get application <app> --namespace argocd -o jsonpath='{.status.resources}{"\n"}' \
  | python3 -m json.tool
```

A resource whose only diff is `replicas` while an HPA targets it confirms the
`ignoreDifferences` hypothesis directly.

## Remediation
Add `ignoreDifferences` for controller-owned fields, correct sync-wave
ordering for CRD-then-CR applies, fix the RBAC granted to ArgoCD's
ServiceAccount, or repair the broken chart/values in the source repository.
For a `Degraded` health with `Synced` sync, remediate the underlying resource
through its own runbook — do not treat this as an ArgoCD problem.

## Blast Radius
Triggering a manual sync re-applies the **entire** tracked manifest set for
that Application, not only the resource under investigation — every tracked
object can be touched in one operation. With `selfHeal` enabled, a sync also
reverts any manual `kubectl` changes made directly against the cluster since
the last sync. Terminating an in-progress operation aborts whatever hook was
mid-run, which may leave a PreSync job partially applied.

## Human Approval Required
- `argocd app sync <app>` / annotating the Application to force a sync
- `kubectl patch application <app> --namespace argocd --type=merge -p '{"spec":{"syncPolicy":{...}}}'`
- Terminating an in-progress sync operation
- `argocd app delete <app>` — **DESTRUCTIVE**, and with cascade enabled deletes every resource it manages

## Verification
```bash
kubectl get application <app> --namespace argocd \
  -o jsonpath='{.status.sync.status}{"\t"}{.status.health.status}{"\n"}'
```
Verified when this reads `Synced` and `Healthy` together, and stays that way
across the next auto-refresh (default ~3 minutes) rather than flipping back to
`OutOfSync` immediately — a fix that only holds for one comparison cycle is not
a fix.

## Rollback
The GitOps-correct rollback is a Git revert followed by a resync, not a direct
`kubectl` edit — with `selfHeal` on, a manual edit is reverted automatically at
the next reconcile regardless. If `ignoreDifferences` was added incorrectly, it
can hide a real drift on that field going forward; remove it once the actual
cause is fixed rather than leaving it as a permanent suppression.

## Related Runbooks
- [../deployments/rollout-rollback.md](../deployments/rollout-rollback.md)
- [../workloads/job-failures.md](../workloads/job-failures.md)
- [../security/rbac-forbidden.md](../security/rbac-forbidden.md)
- [../helm/helm-troubleshooting.md](../helm/helm-troubleshooting.md)

## Official Documentation
- [Argo CD - Application Health](https://argo-cd.readthedocs.io/en/stable/operator-manual/health/)
- [Argo CD - Diffing Customization](https://argo-cd.readthedocs.io/en/stable/user-guide/diffing/)
- [Argo CD - Sync Phases and Waves](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/)
