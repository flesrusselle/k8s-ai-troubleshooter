# Safety Model & Command Safety Classification

`k8s-ai-troubleshooter` enforces a strict 4-level safety classification for every Kubernetes command.

---

## 🛡️ Safety Classifications

### 1. `SAFE_READ`
Read-only queries that do not alter resource status or cluster configuration.
* **Commands**: `kubectl get`, `kubectl describe`, `kubectl logs`, `kubectl top`, `kubectl explain`, `helm list`, `helm status`, `helm get values`.
* **Execution**: Fully automated diagnostic gathering allowed.

### 2. `SAFE_DIAGNOSTIC`
Commands designed for troubleshooting.
* **Commands**: `kubectl top pods`, `kubectl explain`.
* **Note on `kubectl debug`**: Commands like `kubectl debug` that attach ephemeral containers or modify node state must NOT be classified as automatically safe. They require `HUMAN_APPROVAL_REQUIRED`.

### 3. `HUMAN_APPROVAL_REQUIRED`
State-changing commands that alter workload state, scaling, configuration, or deployments.
* **Commands**: `kubectl rollout restart`, `kubectl scale`, `kubectl patch`, `kubectl apply`, `kubectl replace`, `kubectl edit`, `helm upgrade`, `helm rollback`.
* **Execution**: Automated execution is **STRICTLY FORBIDDEN**. Must show exact command, expected impact, and pause for human consent.

### 4. `DESTRUCTIVE`
Operations that permanently destroy data, workloads, volumes, or namespaces.
* **Commands**: `kubectl delete namespace`, `kubectl delete pod --force`, `kubectl delete pvc`, `helm uninstall`.
* **Execution**: Automated execution is **STRICTLY FORBIDDEN**. Requires multi-step human verification.

---

## 🚫 Absolute Safety Enforcements

AI systems integrating `k8s-ai-troubleshooter` must strictly follow:

```text
NEVER automatically execute a command that:
- deletes resources
- restarts workloads
- changes replicas
- modifies resources
- patches resources
- applies manifests
- upgrades Helm releases
- rolls back Helm releases
- uninstalls Helm releases
- changes cluster configuration
- changes networking or storage
```

---

## Enforcement has two layers, not one

Everything above is enforced in **application logic** — `scripts/safety.py`
classifying a command, `scripts/collect.py` refusing to run anything above
`SAFE_DIAGNOSTIC`. That holds as long as the assistant is behaving correctly.
It does not hold against a bug, a prompt injection, or a compromised
dependency, because the application is still running under whatever
Kubernetes permissions its kubeconfig has.

`manifests/rbac/` is the second layer: a `ClusterRole` that grants only the
verbs this project's own classification calls `SAFE_READ`/`SAFE_DIAGNOSTIC` —
no `create`, `patch`, `delete`, on anything. Bind the identity running this
tool to it, and the "never execute a mutating command" rule above is enforced
by the Kubernetes API server itself, independent of whether the application
code is behaving. See [`manifests/rbac/README.md`](../manifests/rbac/README.md),
including the Secrets/Helm tradeoff before choosing which variant to bind.
