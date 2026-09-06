# Helm Integration & Release Ownership

Helm is a first-class citizen in `k8s-ai-troubleshooter`.

The current integration is Helm 3-oriented and read-only. It inspects releases
through the local `helm` binary and Kubernetes objects through `kubectl`; it
does not install charts or change releases automatically.

---

## 🔍 Identifying Helm Ownership

When investigating a failing Kubernetes resource (Deployment, StatefulSet, Pod, Service, ConfigMap), inspect metadata labels and annotations:

```bash
# Inspect Helm ownership labels
kubectl get deployment <name> -o jsonpath='{.metadata.labels.app\.kubernetes\.io/managed-by}'

# Retrieve Helm release name
kubectl get deployment <name> -o jsonpath='{.metadata.annotations.meta\.helm\.sh/release-name}'
```

---

## 🛠️ Helm Diagnostic Commands (`SAFE_READ`)

```bash
# List all Helm releases across all namespaces
helm list -A

# Check status of a release
helm status <release-name> --namespace <namespace>

# View release active values
helm get values <release-name> --namespace <namespace>

# View rendered manifests
helm get manifest <release-name> --namespace <namespace>

# View release revision history
helm history <release-name> --namespace <namespace>
```

---

## 🛑 State-Changing Helm Remediation (`HUMAN_APPROVAL_REQUIRED`)

Never execute these automatically:

```bash
# Upgrading Helm release
helm upgrade <release-name> <chart> -f values.yaml

# Rolling back Helm release
helm rollback <release-name> <revision>

# Uninstalling Helm release (DESTRUCTIVE)
helm uninstall <release-name> --namespace <namespace>
```

## Helmfile

Helmfile is not currently a native collector backend or MCP tool. It can still
be used alongside this repository as the source of desired release state:

```bash
# Review the declared state without changing the cluster.
helmfile -e <environment> list
helmfile -e <environment> template --skip-deps > rendered.yaml

# Then inspect the live release and Kubernetes resources.
helm list -A
helm status <release-name> --namespace <namespace>
kubectl get deploy,pods,events --namespace <namespace>
```

Do not treat every Helmfile subcommand as read-only. `helmfile apply`, `sync`,
`destroy`, and commands that invoke chart hooks can change the cluster or run
arbitrary chart-defined behavior. They are outside the collector's automatic
execution path and require explicit human review.

For a Helmfile-managed incident, include the relevant environment, release
name, chart version, Git revision, values-file names, and rendered manifest
diff in the incident context. Redact rendered output before sharing it because
values files and templates may contain credentials or internal endpoints.

## Kubernetes version guidance

The project does not pin one Kubernetes minor release. Use the cluster's
supported `kubectl` version skew, prefer APIs currently served by the target
cluster, and check the [official Kubernetes version-skew policy](https://kubernetes.io/releases/version-skew-policy/)
before upgrades. Helm chart compatibility remains chart-specific: test the
rendered manifests against the target cluster and review deprecated API warnings
before applying a release.
