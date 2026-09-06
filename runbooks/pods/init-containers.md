# Init Container Failure Runbook

## Purpose
Diagnose pods stuck in `Init:*` states, where an init container fails before the
application container is ever started.

## When to Use
Pod status begins with `Init:` — `Init:0/2`, `Init:Error`,
`Init:CrashLoopBackOff` — or the pod sits in `PodInitializing` indefinitely.

## Safety Level
`SAFE_READ`

## Symptoms
- Pod status `Init:CrashLoopBackOff`, `Init:Error`, or `Init:0/1`.
- `READY` column shows `0/1` and never advances.
- `kubectl logs <pod>` returns "container not found" or logs from the wrong container.
- Application logs are empty because the app never started.

## Quick Diagnosis

The critical detail: **plain `kubectl logs` does not show init container output.**
You must name the container explicitly, which is why this failure is so often
misread as "no logs at all".

```bash
# 1. Identify the init containers and which one is failing
kubectl get pod <pod-name> --namespace <namespace> \
  -o jsonpath='{range .status.initContainerStatuses[*]}{.name}{"\t"}{.state}{"\n"}{end}'

# 2. Logs from the failing init container — note -c
kubectl logs <pod-name> --namespace <namespace> -c <init-container-name>

# 3. Previous attempt, if it is crash-looping
kubectl logs <pod-name> --namespace <namespace> -c <init-container-name> --previous

# 4. Full state including exit codes
kubectl describe pod <pod-name> --namespace <namespace>
```

## Detailed Investigation

```text
Init:* state
       ↓
Which init container? (initContainerStatuses)
       ↓
Init:0/N          → first init container has not completed
Init:Error        → init container exited non-zero
Init:CrashLoopBackOff → init container failing repeatedly
Init:ImagePullBackOff → init container image cannot be pulled
       ↓
Read that container's logs with -c <name>
       ↓
Exit code 1   → application logic failed (dependency not ready?)
Exit code 127 → command not found in the init image
Timeout       → waiting on a dependency that will never arrive
```

1. **Init containers run in order, one at a time.** `Init:1/3` means the first
   succeeded and the second is running or failing. Containers after the failure
   point have never executed, so their logs are empty by definition — this is
   normal, not a second fault.
2. **The most common init container is a dependency wait.** A loop polling for a
   database, a migration job, or a config service. If that dependency is broken,
   the init container is reporting the truth: the real fault is elsewhere.
3. **Restart semantics differ.** An init container that fails is restarted
   according to the pod's `restartPolicy`. With `restartPolicy: Never`, the whole
   pod moves to `Failed` on the first init failure.
4. **Native sidecars** (init containers with `restartPolicy: Always`, Kubernetes
   1.29+) start and keep running. If one of those never becomes ready, the pod
   stays initializing forever with no error at all.

## Decision Tree
`decision-trees/pod-failure.yaml`

## Evidence to Collect
- Ordered list of init containers and each one's state and exit code.
- Logs of the failing init container, current and `--previous`.
- What external dependency the init container waits on, and whether it is healthy.
- ConfigMaps, Secrets and volumes the init container mounts.
- `restartPolicy` of the pod.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| Init container loops with "waiting for..." | Dependency genuinely unavailable — investigate the dependency, not this pod | High |
| `Init:Error`, exit code 1, migration script output | Database migration failed; app must not start | High |
| Exit code 127 | Binary missing from the init image, or wrong `command` | High |
| `Init:ImagePullBackOff` | Init image tag wrong or registry auth missing | High |
| `Init:0/1` for many minutes, no logs at all | Init container blocked on a network call with no timeout | Medium |
| Pod initializing forever, init container healthy | Native sidecar never reports ready | Medium |

## Confirmation
Confirm by resolving the init container's own dependency and observing the pod
advance:

```bash
kubectl get pod <pod-name> --namespace <namespace> -w
```

The `STATUS` should progress `Init:0/1` → `PodInitializing` → `Running`. If it
does not advance after the dependency is healthy, the init container's check
logic is wrong rather than its subject.

## Remediation
Fix the dependency the init container is waiting for, correct its image or
`command`, or — if the init container is enforcing a precondition that no longer
applies — remove it from the pod spec. Do not "fix" a failing init container by
deleting it if it guards data integrity, such as a schema migration.

## Blast Radius
Fixing the dependency an init container waits on usually affects the
dependency's own consumers, not just this pod. Removing an init container
removes whatever precondition it enforced — if it guarded a schema migration,
that is a data-integrity change, not a scheduling one.

## Human Approval Required
- `kubectl rollout restart deployment/<name> --namespace <namespace>`
- `kubectl apply -f <corrected-manifest>.yaml`

## Verification
```bash
kubectl get pod <pod-name> --namespace <namespace> \
  -o jsonpath='{.status.initContainerStatuses[*].state}{"\n"}'
```
Verified when every init container reports `terminated` with `exitCode: 0` and
the pod advances to `Running`. Watch the transition rather than sampling once —
an init container that succeeds and then fails on a later restart looks
identical at a single point in time.

## Rollback
Restore the previous pod template with `kubectl rollout undo`. If an init
container was removed and it guarded a migration or precondition, rolling back
restores the guard but not any state changed while it was absent.

## Related Runbooks
- [crashloopbackoff.md](crashloopbackoff.md)
- [imagepullbackoff.md](imagepullbackoff.md)
- [pending.md](pending.md)
- [../networking/coredns.md](../networking/coredns.md)

## Official Documentation
- [Init Containers](https://kubernetes.io/docs/concepts/workloads/pods/init-containers/)
- [Debug Init Containers](https://kubernetes.io/docs/tasks/debug/debug-application/debug-init-containers/)
