# Pod Security Admission Runbook

## Purpose
Diagnose pods rejected by Pod Security Admission (PSA), the built-in admission
controller that enforces the Pod Security Standards.

## When to Use
Errors containing `violates PodSecurity`, or workloads that stopped deploying
after a namespace was labelled, a cluster was upgraded, or PodSecurityPolicy was
removed.

## Safety Level
`SAFE_READ`

## Symptoms
- `Error creating: pods "x-" is forbidden: violates PodSecurity "restricted:latest"`.
- A Deployment exists with `0/3` replicas and **no pods at all**.
- Warnings on apply that do not block, then silent failure later.
- Charts that installed fine last quarter now refuse to run.

## Quick Diagnosis

The trap here: the Deployment is created successfully and the *ReplicaSet* is
rejected, so `kubectl get pods` shows nothing and `describe deployment` looks
healthy. The error is on the ReplicaSet.

```bash
# 1. The real error lives here, not on the Deployment
kubectl describe replicaset -n <namespace> | grep -A5 FailedCreate

# 2. What level is the namespace enforcing?
kubectl get namespace <namespace> -o jsonpath='{.metadata.labels}'

# 3. Test a manifest against a policy without applying it
kubectl label --dry-run=server --overwrite ns <namespace> \
  pod-security.kubernetes.io/enforce=restricted

# 4. What the workload actually asks for
kubectl get deployment <name> -n <namespace> \
  -o jsonpath='{.spec.template.spec.securityContext}{"\n"}{.spec.template.spec.containers[*].securityContext}'
```

## Detailed Investigation

```text
violates PodSecurity
       ↓
Read the violation list — it names every failing field
       ↓
Which level? privileged / baseline / restricted
       ↓
restricted requires ALL of:
  runAsNonRoot: true
  allowPrivilegeEscalation: false
  capabilities.drop: ["ALL"]
  seccompProfile.type: RuntimeDefault | Localhost
       ↓
Is the requirement real for this workload?
       ↓ yes → the workload genuinely needs the privilege; exempt deliberately
       ↓ no  → add the missing securityContext fields
```

1. **Three levels, three behaviours.** `privileged` allows everything;
   `baseline` blocks known privilege escalations; `restricted` additionally
   demands hardening the pod must opt into explicitly.
2. **Three modes, and only one blocks.** `enforce` rejects, `audit` records to
   the audit log, `warn` returns a warning to the client. A namespace can carry
   all three at different levels — a `warn` you ignored in staging becomes an
   `enforce` rejection in production.
3. **The violation message is a complete checklist.** It enumerates every field
   that failed, not just the first. Fix them in one pass.
4. **`restricted` requires opting in, not merely avoiding bad settings.** A pod
   with no `securityContext` at all fails `restricted`, because
   `runAsNonRoot`, `seccompProfile` and dropped capabilities must be stated.

## Decision Tree
Self-contained; the violation message enumerates the failing fields directly.

## Evidence to Collect
- The full `violates PodSecurity` message with its field list.
- Namespace labels: `pod-security.kubernetes.io/{enforce,audit,warn}` and their versions.
- The pod template's `securityContext`, both pod-level and per-container.
- Whether the image genuinely requires root — check its `USER` directive.
- Whether the cluster was recently upgraded, or PSP was removed.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| `runAsNonRoot != true` | No `securityContext`; image runs as root by default | High |
| `seccompProfile` not set | `restricted` requires it explicitly | High |
| `unrestricted capabilities` | Missing `capabilities.drop: ["ALL"]` | High |
| `allowPrivilegeEscalation != false` | Field not set; the default is permissive | High |
| Deployment shows 0 replicas, no pods, no events | ReplicaSet rejected — look at the ReplicaSet | High |
| Broke after a cluster upgrade | PSP removed, PSA now enforcing | Medium |
| `hostPath` / `hostNetwork` rejected | `baseline` violation — usually a genuine design issue | High |

## Confirmation
Confirm by dry-running the namespace label change, which reports every workload
that would be rejected without changing anything:

```bash
kubectl label --dry-run=server --overwrite ns <namespace> \
  pod-security.kubernetes.io/enforce=restricted
```

This is also the correct way to plan a migration: run it before you enforce.

## Remediation
Add the required `securityContext` fields to the pod template. If the workload
genuinely needs a privilege — a CNI agent, a node exporter — exempt it
deliberately by running it in a namespace labelled `privileged`, rather than
lowering the level of a shared namespace.

## Human Approval Required
- `kubectl apply -f <hardened-manifest>.yaml`
- `kubectl label namespace <ns> pod-security.kubernetes.io/enforce=<level>` — changes policy for every workload in the namespace

## Related Runbooks
- [rbac-forbidden.md](rbac-forbidden.md)
- [admission-webhook.md](admission-webhook.md)
- [../deployments/deployment-stuck.md](../deployments/deployment-stuck.md)
- [../pods/crashloopbackoff.md](../pods/crashloopbackoff.md)

## Official Documentation
- [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
- [Pod Security Admission](https://kubernetes.io/docs/concepts/security/pod-security-admission/)
