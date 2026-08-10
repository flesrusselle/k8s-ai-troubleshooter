# Pod State Reference

The `STATUS` column of `kubectl get pods` is not the pod's `phase`. It is a
synthesised string that kubectl builds from the phase, container waiting
reasons, and init container progress. Knowing which of those you are looking at
determines where to look next.

---

## Phases — there are only five

| Phase | Meaning |
| :--- | :--- |
| `Pending` | Accepted by the API server, not yet running. Either unscheduled, or pulling images |
| `Running` | Bound to a node with at least one container running. **Does not mean healthy** |
| `Succeeded` | All containers terminated successfully and will not restart |
| `Failed` | All containers terminated, at least one non-zero, and will not restart |
| `Unknown` | The node's state cannot be obtained — usually a node or network fault |

`Running` and `Ready` are independent. A pod can be `Running` with `0/1` ready
and serve no traffic at all — this is the single most misread state in
Kubernetes, and it is why the `READY` column matters more than `STATUS`.

---

## Container waiting reasons

These appear in `status.containerStatuses[].state.waiting.reason` and are what
kubectl usually surfaces as `STATUS`.

| Reason | Cause | Runbook |
| :--- | :--- | :--- |
| `ContainerCreating` | Sandbox setup, volume mounts, image pull in progress. Normal briefly; a problem after ~2 minutes | [mount-failure.md](../../runbooks/storage/mount-failure.md) |
| `CrashLoopBackOff` | Container repeatedly exits and is restarted with growing backoff | [crashloopbackoff.md](../../runbooks/pods/crashloopbackoff.md) |
| `ImagePullBackOff` | Image pull failed and is being retried | [imagepullbackoff.md](../../runbooks/pods/imagepullbackoff.md) |
| `ErrImagePull` | The immediately preceding pull attempt failed | [imagepullbackoff.md](../../runbooks/pods/imagepullbackoff.md) |
| `InvalidImageName` | Image reference is malformed — a typo, not a registry fault | [imagepullbackoff.md](../../runbooks/pods/imagepullbackoff.md) |
| `CreateContainerConfigError` | A referenced ConfigMap or Secret does not exist | [mount-failure.md](../../runbooks/storage/mount-failure.md) |
| `CreateContainerError` | Runtime refused to create the container | [crashloopbackoff.md](../../runbooks/pods/crashloopbackoff.md) |
| `RunContainerError` | Container created but failed to start | [crashloopbackoff.md](../../runbooks/pods/crashloopbackoff.md) |
| `PodInitializing` | Init containers still running | [init-containers.md](../../runbooks/pods/init-containers.md) |

---

## Terminated reasons

From `status.containerStatuses[].lastState.terminated.reason`.

| Reason | Meaning | Runbook |
| :--- | :--- | :--- |
| `OOMKilled` | Kernel OOM killer terminated it for exceeding its memory limit | [oomkilled.md](../../runbooks/pods/oomkilled.md) |
| `Error` | Exited non-zero for any other reason | [crashloopbackoff.md](../../runbooks/pods/crashloopbackoff.md) |
| `Completed` | Exited zero. Expected for Jobs, a bug for services | [job-failures.md](../../runbooks/workloads/job-failures.md) |
| `ContainerCannotRun` | The runtime could not execute the entrypoint | [crashloopbackoff.md](../../runbooks/pods/crashloopbackoff.md) |
| `DeadlineExceeded` | `activeDeadlineSeconds` elapsed | [job-failures.md](../../runbooks/workloads/job-failures.md) |
| `Evicted` | Kubelet reclaimed node resources | [evicted.md](../../runbooks/pods/evicted.md) |

---

## Composite STATUS strings kubectl invents

These are not phases or reasons — kubectl assembles them, which is why searching
the API reference for them finds nothing.

| STATUS | Meaning |
| :--- | :--- |
| `Init:0/2` | First of two init containers has not completed |
| `Init:Error` | An init container exited non-zero |
| `Init:CrashLoopBackOff` | An init container is crash-looping |
| `Terminating` | Deletion requested; grace period running or finalizers pending |
| `Completed` | Every container exited zero |
| `NodeAffinity` | Evicted because it no longer satisfies its node affinity |
| `Evicted` | Removed by kubelet under resource pressure |
| `Unknown` | The node stopped reporting |

A pod stuck in `Terminating` for more than its grace period usually has a
finalizer or a hung runtime — see
[multi-attach.md](../../runbooks/storage/multi-attach.md) when a volume is
involved.

---

## Finding unhealthy pods correctly

A phase filter misses the most important case:

```bash
# Misses pods that are Running but not Ready
kubectl get pods -A --field-selector=status.phase!=Running

# Catches partially-ready pods too
kubectl get pods -A -o json | python3 -c "
import sys, json
for p in json.load(sys.stdin)['items']:
    cs = p['status'].get('containerStatuses', [])
    if not cs: continue
    ready = sum(1 for c in cs if c['ready'])
    if ready < len(cs) and p['status']['phase'] != 'Succeeded':
        print(f\"{p['metadata']['namespace']}/{p['metadata']['name']} {ready}/{len(cs)}\")
"
```

`scripts/collect.py` applies both checks for this reason.

---

## Related

- [exit-codes.md](exit-codes.md)
- [event-reasons.md](event-reasons.md)
- [../../symptom-index.yaml](../../symptom-index.yaml) — route any of these to a runbook
