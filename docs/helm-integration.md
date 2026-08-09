# Helm Integration & Release Ownership

Helm is a first-class citizen in `k8s-ai-troubleshooter`.

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
helm status <release-name> -n <namespace>

# View release active values
helm get values <release-name> -n <namespace>

# View rendered manifests
helm get manifest <release-name> -n <namespace>

# View release revision history
helm history <release-name> -n <namespace>
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
helm uninstall <release-name> -n <namespace>
```
