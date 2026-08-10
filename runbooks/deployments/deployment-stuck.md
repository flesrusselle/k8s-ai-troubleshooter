# Stuck Deployment Rollout Runbook

## Purpose
Diagnose Kubernetes Deployments stuck during rolling updates without reaching desired ready replica counts.

## When to Use
Triggered when `kubectl rollout status deployment/<name>` hangs or reports `ProgressDeadlineExceeded`.

## Safety Level
`SAFE_READ`

## Symptoms
- Deployment status: `ProgressDeadlineExceeded`.
- Replicas stuck at e.g. `2 updated / 1 ready / 3 total`.

## Quick Diagnosis

```bash
# 1. Check deployment rollout status
kubectl rollout status deployment/<deployment-name> -n <namespace>

# 2. Inspect ReplicaSets created by deployment
kubectl get rs -n <namespace> -l app=<app-label>

# 3. Inspect status of pods owned by new ReplicaSet
kubectl describe pod -n <namespace> -l pod-template-hash=<new-hash>
```

## Detailed Investigation

Traverse owner hierarchy:

```text
Deployment
    └── ReplicaSet (New)
            └── Pods (New) -> ImagePullBackOff / CrashLoopBackOff / Pending
```

1. **Identify Active ReplicaSets**: Find which ReplicaSet represents the new revision.
2. **Inspect New Pods**: Query pods belonging to the new ReplicaSet to see why they are unready.

## Decision Tree
`decision-trees/pod-failure.yaml`

## Evidence to Collect
- Deployment rollout status.
- New vs old ReplicaSet pod counts.
- New pod failure reason.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| New pods `ImagePullBackOff` | Bad image tag specified in rollout update | High |
| New pods failing readiness probe | New application revision failing health check | High |

## Confirmation
Identify specific failure in new ReplicaSet pods blocking deployment progress deadline.

## Remediation
Undo deployment rollout to last working revision or fix container image/config.

## Blast Radius
Rollout changes replace pods across the workload. Raising `maxSurge` consumes
additional cluster capacity during the rollout and can push a namespace over its
ResourceQuota, blocking unrelated deployments.

## Human Approval Required
- `kubectl rollout undo deployment/<deployment-name> -n <namespace>` (**HUMAN APPROVAL REQUIRED**)

## Verification
```bash
kubectl rollout status deployment/<name> -n <namespace> --timeout=120s
kubectl get deployment <name> -n <namespace>
```
Verified when `rollout status` reports success and `READY` matches the desired
replica count. `UP-TO-DATE` alone is not enough — it counts pods with the new
template, including ones that are not ready.

## Rollback
`kubectl rollout undo deployment/<name> -n <namespace>` restores the previous
template as a new revision. Only `revisionHistoryLimit` revisions are retained,
so an old target may no longer exist.

## Related Runbooks
- [crashloopbackoff.md](../pods/crashloopbackoff.md)
- [probes.md](../pods/probes.md)

## Official Documentation
- [Deployment Rollouts](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#updating-a-deployment)
