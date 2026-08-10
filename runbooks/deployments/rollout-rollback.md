# Rollout & Rollback Runbook

## Purpose
Investigate a bad release and establish what changed, so a rollback is an
informed decision rather than a reflex.

## When to Use
A deploy has just gone out and something is worse than it was — errors, latency,
crashes — and you need to decide between rolling back and fixing forward.

## Safety Level
`SAFE_READ`

## Symptoms
- Error rate rose immediately after a deploy.
- New pods are unhealthy while old ones were fine.
- A rollout is partially complete with both versions running.
- Nobody is certain what actually changed.

## Quick Diagnosis

```bash
# 1. Where is the rollout now?
kubectl rollout status deployment/<name> -n <namespace> --timeout=30s

# 2. Revision history
kubectl rollout history deployment/<name> -n <namespace>

# 3. What the previous revision looked like
kubectl rollout history deployment/<name> -n <namespace> --revision=<n>

# 4. Both generations of pods, side by side
kubectl get pods -n <namespace> -l app=<label> \
  -o custom-columns='NAME:.metadata.name,IMAGE:.spec.containers[0].image,STATUS:.status.phase,AGE:.metadata.creationTimestamp'
```

## Detailed Investigation

```text
Bad release
       ↓
Is the rollout complete, or half-done?
       ↓ half-done → both versions serving; symptoms may be intermittent
       ↓ complete
What changed between revisions?
       ↓
Image tag?     → new application code
Env / ConfigMap? → configuration; note that a ConfigMap change alone
                   does NOT create a new revision
Resources?     → limits may now be too low; watch for OOMKills
Probes?        → a stricter probe can kill a healthy app
       ↓
Are new pods failing, or serving errors?
       ↓ failing → ordinary pod debugging
       ↓ serving errors → application regression
```

1. **A partially complete rollout serves both versions.** Intermittent errors
   proportional to the split are the signature. `kubectl rollout status` tells
   you the split; the proportion of failures should match it.
2. **`rollout history` only records pod template changes.** A ConfigMap or Secret
   edit consumed by the pods changes behaviour without creating a revision, and
   is therefore invisible in the history. When history shows nothing and
   behaviour changed anyway, look there.
3. **`CHANGE-CAUSE` is empty unless someone recorded it.** Do not read a blank
   column as "nothing changed".
4. **Rollback is a forward operation.** It creates a *new* revision with the old
   template. History grows; it does not rewind.
5. **Rollback does not undo side effects.** Database migrations, published
   messages, and mutated external state persist. For a release that migrated a
   schema, rolling back the code can be worse than the bug.
6. **`revisionHistoryLimit` caps what you can return to** — default 10. Beyond
   that, old revisions are gone.

## Decision Tree
`decision-trees/pod-failure.yaml` when the new pods are themselves failing.

## Evidence to Collect
- Current rollout status and how many replicas are on each revision.
- Diff between the current and previous revision's pod template.
- Whether any ConfigMap or Secret consumed by the workload changed recently.
- Health of the new pods versus the old.
- Whether the release included a migration or other irreversible side effect.
- Error-rate onset time versus rollout start time.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| New pods CrashLoopBackOff, old fine | Application or config regression in the new image | High |
| Errors proportional to rollout progress | Both versions serving; new one is broken | High |
| New pods OOMKilled | Memory limits unchanged, new version needs more | High |
| Rollout stalls at `maxSurge` | No capacity, or a quota ceiling | High |
| Behaviour changed, history shows nothing | ConfigMap or Secret changed without a new revision | High |
| `ProgressDeadlineExceeded` | New pods never became Ready | High |
| Rollback did not help | Side effects persist, or the cause was never the deploy | Medium |

## Confirmation
Confirm the release is implicated by comparing pod health across revisions:

```bash
kubectl get pods -n <namespace> -l app=<label> \
  -o custom-columns='POD:.metadata.name,REVISION:.metadata.labels.pod-template-hash,READY:.status.conditions[?(@.type=="Ready")].status'
```

All unready pods sharing one `pod-template-hash` while the other hash is healthy
confirms the new revision, and makes rollback the correct action. Failures spread
across both hashes mean the deploy is coincidental — keep investigating.

## Remediation
Roll back to the last known-good revision if the new one is the confirmed cause
and the release had no irreversible side effects. Otherwise fix forward. Record
a `CHANGE-CAUSE` on the next release so the same investigation is cheaper.

## Blast Radius
A rollback replaces every pod, exactly like the deploy that caused the
problem. It does not undo side effects: completed database migrations, published
messages, and mutated external state persist. For a release that migrated a
schema, rolling back the code can be worse than the bug.

## Human Approval Required
- `kubectl rollout undo deployment/<name> -n <namespace>` — replaces every running pod
- `kubectl rollout undo deployment/<name> --to-revision=<n> -n <namespace>`
- `kubectl rollout pause deployment/<name> -n <namespace>` — freezes a partial rollout, leaving both versions serving
- `kubectl rollout restart deployment/<name> -n <namespace>`

## Verification
```bash
kubectl rollout status deployment/<name> -n <namespace>
kubectl get pods -n <namespace> -l app=<label> \
  -o custom-columns='POD:.metadata.name,REVISION:.metadata.labels.pod-template-hash,READY:.status.conditions[?(@.type=="Ready")].status'
```
Verified when every pod carries the target revision's `pod-template-hash`, all
are Ready, and the symptom that prompted the rollback is measurably gone. Pod
health alone does not prove the user-facing problem was resolved.

## Rollback
A rollback is itself rolled back with another `rollout undo`, since each
creates a new revision. Irreversible side effects of the original release remain
irreversible in both directions — establish whether any exist before choosing
rollback over fixing forward.

## Related Runbooks
- [deployment-stuck.md](deployment-stuck.md)
- [../pods/crashloopbackoff.md](../pods/crashloopbackoff.md)
- [../pods/oomkilled.md](../pods/oomkilled.md)
- [../helm/helm-troubleshooting.md](../helm/helm-troubleshooting.md)

## Official Documentation
- [Rolling Back a Deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#rolling-back-a-deployment)
- [Deployment Strategy](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#strategy)
