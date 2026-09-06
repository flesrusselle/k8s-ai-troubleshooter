# RBAC for k8s-ai-troubleshooter

Every other safety control in this repository — the classifier in
`scripts/safety.py`, the refusal to auto-execute above `SAFE_DIAGNOSTIC`,
`collect.py`'s guard in front of the subprocess — is enforced in **application
logic**. That is real, but it only holds while the assistant is behaving. RBAC
is the layer that holds even if it isn't: bind the identity running this tool
to a role that physically cannot mutate the cluster, and no prompt injection,
bug, or compromised dependency changes that.

That's what this directory is for. Apply it and run `collect.py` — or any
agentic integration — under a kubeconfig for the `k8s-ai-troubleshooter`
ServiceAccount instead of your personal or cluster-admin one.

## Apply it

```bash
kubectl apply -f manifests/rbac/namespace.yaml
kubectl apply -f manifests/rbac/serviceaccount.yaml
kubectl apply -f manifests/rbac/clusterrole-readonly.yaml
kubectl apply -f manifests/rbac/clusterrolebinding.yaml
```

Generate a kubeconfig scoped to that identity (Kubernetes 1.24+, where
ServiceAccount tokens are no longer auto-created as long-lived Secrets):

```bash
kubectl create token k8s-ai-troubleshooter --namespace k8s-ai-troubleshooter --duration=8h
```

Use the resulting token as a bearer token in a kubeconfig pointed at your
cluster's API server, or — if running the collector as an in-cluster
CronJob — mount the ServiceAccount directly and let the in-cluster
configuration pick it up with no kubeconfig at all.

## Secrets and Helm

Read this before choosing which ClusterRole to bind.

**`clusterrole-readonly.yaml` grants `get`/`list` on Secrets.** This is not
optional if you want Helm diagnosis: Helm 3's default release storage backend
*is* Secrets (`type: helm.sh/release.v1`), so `helm list`, `helm status`,
`helm get`, and `helm history` — and the `helm-releases` step in
`scripts/collect.py` — cannot function without it.

The uncomfortable part: this grants full secret **value** read to anything
bound to this role, not merely the names `collect.py` chooses to display in
`secrets-metadata.txt`. Kubernetes RBAC has no field-level or metadata-only
restriction on `list` — a client that can list Secrets in a namespace can read
every value in every one of them, regardless of what any particular client
displays. `collect.py` choosing not to show values is an application-level
choice, not an RBAC guarantee.

**`clusterrole-readonly-no-secrets.yaml`** removes the rule entirely. Bind
this if your team wants that stronger boundary. The cost: Helm diagnosis
breaks outright, and `secrets-metadata.txt` in every evidence bundle will show
a `Forbidden` error instead of a list of Secret names. `collect.py` degrades
gracefully — the failure is recorded, not fatal — but Helm's runbooks
(`runbooks/helm/*.md`) become unusable under this role.

There is no third option that gives you Helm support with only metadata-level
secret access; that would require either an API-aggregation layer that
filters Secret reads, or Helm switching its own storage backend away from
Secrets (it supports ConfigMaps and SQL as alternatives, configured on the
Helm client side, not from here).

## Cluster-scoped vs namespace-scoped

`clusterrolebinding.yaml` binds cluster-wide. If your team wants to scope this
to specific namespaces, bind the *same* ClusterRole with a `RoleBinding`
instead — a ClusterRole can be referenced by a namespaced RoleBinding, and
this is the standard way to reuse one role definition at different scopes.

The tradeoff: a RoleBinding cannot authorize the cluster-scoped rules in
either ClusterRole — `nodes`, `namespaces`, `persistentvolumes`,
`storageclasses`, `volumeattachments`, `componentstatuses`, and the
non-resource health-endpoint URLs. Under a namespace-scoped binding,
`runbooks/triage.md`, the node runbooks, and `scripts/collect.py`'s
cluster-wide steps will fail with `Forbidden`. This is the same node-vs-pod
tradeoff every namespaced-RBAC design in Kubernetes runs into — namespace
isolation and cluster-wide triage are in real tension, not a configuration
oversight.

## Keeping this in sync

`tests/test_rbac_manifest.py` parses `scripts/collect.py`'s command plans and
`commands/*.yaml`, and asserts every resource+verb they use has a matching
rule in `clusterrole-readonly.yaml`. A new step added to the collector without
a corresponding RBAC rule fails CI — the manifest cannot silently drift behind
what the tool actually does.
