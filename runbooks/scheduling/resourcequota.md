# ResourceQuota & LimitRange Runbook

## Purpose
Diagnose workloads rejected by namespace-level admission policy: ResourceQuota
exhaustion and LimitRange violations.

## When to Use
Errors containing `exceeded quota`, `must specify limits`, or a Deployment that
reports no pods and no scheduling events at all.

## Safety Level
`SAFE_READ`

## Symptoms
- `pods "x-" is forbidden: exceeded quota: compute-resources, requested: ...`.
- `Deployment shows 0/3` with **no pods created**.
- `must specify limits.memory` on an otherwise valid manifest.
- A namespace that accepted the same workload last week now rejects it.

## Quick Diagnosis

Like Pod Security Admission, this rejects the **ReplicaSet**, not the
Deployment — so `kubectl get pods` shows nothing and the Deployment looks fine.

```bash
# 1. The error is here
kubectl describe replicaset --namespace <namespace> | grep -A5 FailedCreate

# 2. Quota consumption — USED vs HARD is the whole story
kubectl describe resourcequota --namespace <namespace>

# 3. Defaults and bounds imposed on every pod
kubectl describe limitrange --namespace <namespace>

# 4. What is consuming the quota
kubectl get pods --namespace <namespace> \
  -o custom-columns='NAME:.metadata.name,CPU_REQ:.spec.containers[*].resources.requests.cpu,MEM_REQ:.spec.containers[*].resources.requests.memory'
```

## Detailed Investigation

```text
Workload rejected at admission
       ↓
"exceeded quota"                → ResourceQuota is full
"must specify limits/requests"  → LimitRange demands explicit values
"maximum ... is X"              → LimitRange max exceeded
       ↓ (quota full)
Is USED close to HARD?
       ↓ yes → reclaim, or raise the quota
       ↓ no, but still rejected
       → the new pod alone exceeds the remaining headroom;
         quota counts REQUESTS, not usage
```

1. **Quota accounts for requests, not consumption.** A namespace can be at 100%
   of its CPU quota while every pod idles. The scheduler and the quota system
   both work from requests; actual utilisation is irrelevant to admission.
2. **A ResourceQuota that includes `requests.cpu` or `limits.memory` makes those
   fields mandatory.** Every pod in the namespace must then set them, or be
   rejected — which is why adding a quota can break workloads that never changed.
3. **LimitRange does two different jobs.** It supplies **defaults** for pods that
   omit values, and enforces **min/max bounds** on those that set them. A pod can
   therefore be rejected for asking too much *or* silently mutated to a default
   that is too small, and the second case surfaces later as an OOMKill.
4. **Object counts are quota too.** `count/pods`, `count/services`,
   `persistentvolumeclaims` are all quotable. Hitting those produces a rejection
   with no resource figures in it at all.
5. **Rolling updates need headroom.** A rollout briefly runs old and new pods
   together. A namespace at 90% of quota can deploy fine and still fail to
   *update*, because `maxSurge` needs room that is not there.

## Decision Tree
Self-contained; branch on quota exhaustion versus LimitRange violation.

## Evidence to Collect
- The exact rejection message from the ReplicaSet events.
- `kubectl describe resourcequota` output showing `USED` against `HARD`.
- `kubectl describe limitrange`, including defaults and max/min.
- Requests and limits of the workload being rejected.
- `maxSurge` on the Deployment, if the failure is on update rather than create.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| `exceeded quota`, `USED` equals `HARD` | Namespace genuinely full | High |
| `must specify limits.memory` | Quota covers `limits.memory`; pod omits it | High |
| Deployment at 0 replicas, no pods, no scheduling events | ReplicaSet rejected at admission | High |
| Creates work, updates fail | `maxSurge` needs headroom the quota lacks | High |
| Pod OOMKilled with limits nobody set | LimitRange default applied silently | Medium |
| `exceeded quota: count/pods` | Object-count quota, not a resource quota | High |
| Broke with no manifest change | A quota or LimitRange was added to the namespace | High |

## Confirmation
Confirm remaining headroom precisely:

```bash
kubectl get resourcequota --namespace <namespace> \
  -o custom-columns='NAME:.metadata.name,USED:.status.used,HARD:.status.hard'
```

If `USED` plus the pending workload's requests exceeds `HARD`, admission is
behaving correctly and the fix is capacity or cleanup — not the manifest.

## Remediation
Reclaim quota by removing unused workloads, set explicit requests and limits on
the rejected pod, raise the quota, or lower `maxSurge` so the rollout fits.
Raising a quota is a capacity decision for the namespace owner, not a workaround
to apply silently.

## Blast Radius
Raising a quota permits more consumption across the whole namespace and may
push the cluster over capacity. Deleting workloads to reclaim quota removes
running services. Adding a LimitRange default silently applies to every pod
created afterwards.

## Human Approval Required
- `kubectl apply -f <manifest-with-resources>.yaml`
- `kubectl patch resourcequota <name> --namespace <ns> --type=merge -p '{"spec":{"hard":{...}}}'`
- `kubectl delete deployment <name> --namespace <namespace>` to reclaim — **DESTRUCTIVE**

## Verification
```bash
kubectl describe resourcequota --namespace <namespace>
kubectl get deployment <name> --namespace <namespace>
```
Verified when `USED` sits below `HARD` with headroom for a rollout's `maxSurge`,
and the previously rejected workload reaches its desired replica count. Fitting
exactly leaves you unable to deploy.

## Rollback
Restore the previous quota with `kubectl patch`. Workloads deleted to reclaim
quota must be recreated from their manifests — the quota change alone does not
bring them back.

## Related Runbooks
- [../pods/pending.md](../pods/pending.md)
- [../pods/oomkilled.md](../pods/oomkilled.md)
- [../workloads/hpa-not-scaling.md](../workloads/hpa-not-scaling.md)
- [../deployments/deployment-stuck.md](../deployments/deployment-stuck.md)

## Official Documentation
- [Resource Quotas](https://kubernetes.io/docs/concepts/policy/resource-quotas/)
- [Limit Ranges](https://kubernetes.io/docs/concepts/policy/limit-range/)
