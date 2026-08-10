# Service Mesh Sidecar Injection Runbook

## Purpose
Diagnose pods that are missing their expected mesh sidecar (Istio's
`istio-proxy`, Linkerd's `linkerd-proxy`), or whose sidecar is present but
failing.

## When to Use
A pod in a namespace enrolled in the mesh shows fewer containers than
expected (`1/1` instead of `2/2`), or the sidecar container itself is
crashing.

## Safety Level
`SAFE_READ`

## Symptoms
- `kubectl get pods` shows `1/1` where every other pod in the namespace shows
  `2/2`.
- Cross-service calls fail specifically for one workload, not the whole mesh.
- A pod sits at `0/2 Running` for minutes rather than settling within seconds.
- The sidecar container itself is `CrashLoopBackOff`.

## Quick Diagnosis

Injection happens at pod **creation** — this is the fact that explains most
confusion here.

```bash
# 1. Container count and names — is the sidecar even present?
kubectl get pod <pod> -n <namespace> \
  -o jsonpath='{range .spec.containers[*]}{.name}{"\n"}{end}'

# 2. Is the namespace actually enrolled?
kubectl get namespace <namespace> --show-labels

# 3. Per-pod override annotations
kubectl get pod <pod> -n <namespace> -o jsonpath='{.metadata.annotations}{"\n"}'

# 4. Is the injector webhook itself healthy?
kubectl get pods -n istio-system -l app=istiod        # Istio
kubectl get pods -n linkerd -l linkerd.io/control-plane-component=proxy-injector  # Linkerd
kubectl get mutatingwebhookconfigurations | grep -Ei 'istio|linkerd'

# 5. The sidecar's own logs
kubectl logs <pod> -n <namespace> -c istio-proxy --tail=100     # Istio
kubectl logs <pod> -n <namespace> -c linkerd-proxy --tail=100   # Linkerd
```

## Detailed Investigation

```text
Sidecar missing or unhealthy
       ↓
Container count normal (2/2) but sidecar unhealthy?
       ↓ yes → read the sidecar's own logs; skip to root causes below
       ↓ no (container missing)
Is the namespace labelled for injection?
       ↓ no  → injection was never requested — expected, not a fault
       ↓ yes
Does the pod carry an inject:"false" override annotation?
       ↓ yes → deliberate exclusion — expected
       ↓ no
Was the pod created BEFORE the namespace label was added?
       ↓ yes → injection is not retroactive; the pod must be recreated
       ↓ no
Is the injector webhook itself reachable?
       ↓ no  → see admission-webhook.md — pods are created without a
                sidecar because the mutating webhook that would add one
                could not be called, and (depending on failurePolicy) that
                may not even block the create
```

1. **Injection is not retroactive.** Labelling a namespace, or removing an
   `inject: "false"` annotation, does nothing to pods already running. Every
   pod created before the change keeps its original container count until it
   is recreated — a rollout restart, not a label change, is the fix.
2. **A down injector webhook can fail open.** Depending on `failurePolicy`,
   an unreachable sidecar-injector webhook may simply mean pods are created
   *without* a sidecar rather than being rejected — see
   `../security/admission-webhook.md`. This produces a mesh-wide gap with no
   error on the workload side at all.
3. **A brief `0/2` at startup is normal; several minutes is not.** Kubernetes
   readiness gates hold the pod at not-Ready until the sidecar reports ready,
   which normally takes seconds. A sidecar stuck fetching its initial config
   from the control plane (xDS) for minutes indicates the sidecar cannot
   reach it — a control-plane health or network problem, not an injection
   problem.
4. **The legacy (non-CNI) init container needs `NET_ADMIN`/`NET_RAW`.**
   Istio's `istio-init` container sets up iptables rules and requires those
   capabilities. The Kubernetes `restricted` Pod Security Standard forbids
   both — a namespace enforcing `restricted` will show the init container
   failing at admission, not silently. See
   `../security/pod-security-admission.md`; the mesh's own CNI plugin mode
   avoids this entirely by moving the iptables setup out of the pod.
5. **Control plane / data plane version skew produces subtle, not obvious,
   failures.** A sidecar several minor versions behind its control plane can
   connect and appear healthy while silently rejecting configuration it does
   not understand. `istioctl proxy-status` (a separate, read-only CLI) shows
   this directly; from `kubectl` alone, compare the sidecar image tag against
   the control plane's.

## Decision Tree
`decision-trees/pod-failure.yaml` once the sidecar itself is the failing
container; the flow above otherwise.

## Evidence to Collect
- Container names and count on the affected pod versus a healthy sibling.
- Namespace labels and any per-pod injection annotations.
- Pod creation timestamp relative to when the namespace label was changed.
- Mutating webhook configuration and injector pod health.
- The sidecar container's own logs and image tag.
- Whether the namespace enforces a Pod Security Standard that would block
  `NET_ADMIN`/`NET_RAW`.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| `1/1`, namespace correctly labelled, pod is old | Created before the label; injection is not retroactive | High |
| `1/1`, namespace labelled, injector webhook down | Failed-open injection — see admission-webhook.md | High |
| `1/1`, pod has `inject: "false"` annotation | Deliberate exclusion — not a fault | High |
| Init container failing, `NET_ADMIN` denied | Pod Security `restricted` blocking legacy sidecar init | High |
| Sidecar `0/2` for minutes | Cannot reach the control plane's xDS endpoint | Medium |
| Sidecar healthy, but rejects valid-looking config | Control plane / data plane version skew | Medium |
| Sidecar `CrashLoopBackOff` | Resource limits too low for the proxy under load | Medium |

## Confirmation
Confirm the "created before injection was enabled" hypothesis directly:

```bash
kubectl get pod <pod> -n <namespace> -o jsonpath='{.metadata.creationTimestamp}{"\n"}'
kubectl get namespace <namespace> -o jsonpath='{.metadata.labels}{"\n"}'
```

If the pod predates the enrollment change, recreating it — not further
investigation — is the fix.

## Remediation
Recreate affected pods (`kubectl rollout restart`) after correcting namespace
labels or annotations. Restore the injector webhook's health if it is down.
Raise sidecar resource limits if it is being OOMKilled under load. Align
sidecar and control-plane versions during mesh upgrades rather than upgrading
one and leaving the other. For the `NET_ADMIN`/PSA conflict, either exempt the
namespace deliberately or move to the mesh's CNI-based injection mode.

## Blast Radius
A rollout restart to pick up injection changes replaces every pod in the
workload, mesh-wide traffic briefly redistributing during the restart.
Restoring the injector webhook re-enables mutation for every future pod create
in every enrolled namespace, not only the one under investigation.

## Human Approval Required
- `kubectl rollout restart deployment/<name> -n <namespace>`
- `kubectl label namespace <namespace> istio-injection=enabled` (or the Linkerd equivalent)
- `kubectl apply -f <injector-webhook-fix>.yaml`

## Verification
```bash
kubectl get pod <pod> -n <namespace> \
  -o jsonpath='{range .spec.containers[*]}{.name}{"\n"}{end}'
```
Verified when the sidecar container appears and reports `Running` with
`ready: true`, and cross-service calls to/from this workload succeed under
whatever mTLS policy the namespace enforces — presence of the sidecar alone
does not prove traffic is actually flowing correctly through it.

## Rollback
`kubectl rollout undo` restores the previous pod template if a manifest
change caused the regression. Removing an injection label and restarting
strips the sidecar back out — do this deliberately, since a workload that
depends on mesh mTLS will lose connectivity to peers still enforcing it.

## Related Runbooks
- [service-mesh-mtls.md](service-mesh-mtls.md)
- [../security/admission-webhook.md](../security/admission-webhook.md)
- [../security/pod-security-admission.md](../security/pod-security-admission.md)
- [../pods/crashloopbackoff.md](../pods/crashloopbackoff.md)

## Official Documentation
- [Istio - Sidecar Injection](https://istio.io/latest/docs/setup/additional-setup/sidecar-injection/)
- [Linkerd - Automatic Proxy Injection](https://linkerd.io/2/features/proxy-injection/)
- [Istio - Application Requirements](https://istio.io/latest/docs/ops/deployment/application-requirements/)
