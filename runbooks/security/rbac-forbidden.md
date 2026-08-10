# RBAC Forbidden Runbook

## Purpose
Diagnose `Forbidden` errors, where the API server authenticated the caller but
denied the action.

## When to Use
Any error containing `is forbidden:`, `cannot list resource`, or
`User "system:serviceaccount:..." cannot ...` — whether from your own `kubectl`,
a CI pipeline, or a pod's service account.

## Safety Level
`SAFE_READ`

## Symptoms
- `Error from server (Forbidden): pods is forbidden: User "..." cannot list resource "pods"`.
- An operator or controller pod logging permission errors in a loop.
- A workload that ran fine until it was moved to a different namespace.
- CI succeeding locally and failing in-cluster.

## Quick Diagnosis

`kubectl auth can-i` answers the question directly, and does not require you to
read a single RoleBinding:

```bash
# 1. What am I? Authentication, not authorization.
kubectl auth whoami

# 2. Can I do the thing?
kubectl auth can-i list pods -n <namespace>

# 3. Can a specific service account do it?
kubectl auth can-i list pods -n <namespace> \
  --as=system:serviceaccount:<namespace>:<serviceaccount>

# 4. Everything that identity can do here
kubectl auth can-i --list -n <namespace> \
  --as=system:serviceaccount:<namespace>:<serviceaccount>
```

## Detailed Investigation

```text
Forbidden error
       ↓
Read the error literally — it names the identity, verb, and resource
       ↓
Is the identity what you expected?
       ↓ no  → wrong serviceAccountName, or default SA in use
       ↓ yes
Does a Role/ClusterRole grant that verb on that resource?
       ↓ no  → missing rule
       ↓ yes
Is it bound to this identity, in this namespace?
       ↓ no  → RoleBinding missing or in the wrong namespace
       ↓ yes
Is the resource namespaced or cluster-scoped?
       → a Role cannot grant access to cluster-scoped resources
```

1. **Read the error message as data.** It contains the full identity, the verb,
   the resource, and the namespace. Most RBAC debugging is over once you read it
   carefully — the identity is frequently `system:serviceaccount:<ns>:default`,
   which means the workload never set `serviceAccountName`.
2. **Role vs ClusterRole is about the resource, not the grantee.** Nodes,
   PersistentVolumes, StorageClasses and Namespaces are cluster-scoped. No
   `Role` can grant access to them, however the binding is written.
3. **RoleBinding namespace is the namespace it grants in**, not where the
   subject lives. A RoleBinding in `dev` grants nothing in `prod`, even for the
   same service account.
4. **A ClusterRoleBinding grants cluster-wide.** Binding a ClusterRole with a
   RoleBinding scopes it to one namespace; binding it with a ClusterRoleBinding
   does not. Confusing the two is the usual cause of over-permission.

## Decision Tree
Self-contained; `kubectl auth can-i --list` resolves most cases in one command.

## Evidence to Collect
- The exact `Forbidden` message, unedited.
- Output of `kubectl auth can-i --list --as=<identity> -n <namespace>`.
- The pod's `serviceAccountName` (absent means `default`).
- Roles and bindings in the namespace: `kubectl get role,rolebinding -n <ns>`.
- Whether the resource is namespaced: `kubectl api-resources --namespaced=true`.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| Identity is `...:<ns>:default` | Workload never set `serviceAccountName` | High |
| Works in one namespace, not another | RoleBinding exists only in the working namespace | High |
| Denied on nodes / PVs / namespaces | Cluster-scoped resource granted via a Role instead of ClusterRole | High |
| Denied on a CRD only | ClusterRole missing the CRD's apiGroup | High |
| Verb `list` allowed, `watch` denied | Rule enumerates verbs individually and omitted `watch` | Medium |
| Was working, now denied | Binding removed, or the operator that manages it was reconciled | Medium |

## Confirmation
Confirm by impersonating the identity and asserting the specific verb:

```bash
kubectl auth can-i <verb> <resource> -n <namespace> \
  --as=system:serviceaccount:<namespace>:<serviceaccount>
```

`yes` while the workload still fails means the workload is using a different
identity than you think — re-check `serviceAccountName` on the pod spec.

## Remediation
Grant the minimum missing rule. Prefer a namespaced Role and RoleBinding over a
ClusterRole; prefer adding one verb over adding a wildcard. `cluster-admin` is
never the answer to a specific denial.

## Human Approval Required
- `kubectl apply -f <role>.yaml`
- `kubectl create rolebinding <name> --role=<role> --serviceaccount=<ns>:<sa> -n <ns>`
- `kubectl create clusterrolebinding ...` — grants cluster-wide, review carefully

## Related Runbooks
- [../pods/crashloopbackoff.md](../pods/crashloopbackoff.md)
- [admission-webhook.md](admission-webhook.md)
- [pod-security-admission.md](pod-security-admission.md)
- [../cluster/cluster-health.md](../cluster/cluster-health.md)

## Official Documentation
- [RBAC Authorization](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
- [Authorization Overview](https://kubernetes.io/docs/reference/access-authn-authz/authorization/)
