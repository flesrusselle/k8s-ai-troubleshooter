# Container Exit Code Reference

The exit code is the cheapest, highest-signal fact about a dead container. It
narrows the cause before a single log line is read, and it is available from
`describe` without hunting for the right container name.

```bash
kubectl get pod <pod> --namespace <namespace> \
  -o jsonpath='{range .status.containerStatuses[*]}{.name}{"\t"}{.lastState.terminated.exitCode}{"\t"}{.lastState.terminated.reason}{"\n"}{end}'
```

---

## The codes you will actually see

| Code | Meaning | What it tells you | Runbook |
| ---: | :--- | :--- | :--- |
| **0** | Clean exit | The process finished successfully. For a long-running service this is still a bug — it was not supposed to return | [restarts.md](../../runbooks/pods/restarts.md) |
| **1** | Generic application error | Uncaught exception, failed startup validation, bad config. The **most common** real failure | [crashloopbackoff.md](../../runbooks/pods/crashloopbackoff.md) |
| **2** | Shell misuse | Malformed shell in `command`/`args`, or a misused builtin | [crashloopbackoff.md](../../runbooks/pods/crashloopbackoff.md) |
| **126** | Command found but not executable | Missing execute bit, or a script whose interpreter line is wrong | [crashloopbackoff.md](../../runbooks/pods/crashloopbackoff.md) |
| **127** | Command not found | Bad `ENTRYPOINT`/`command`, wrong architecture, or a binary absent from the image | [crashloopbackoff.md](../../runbooks/pods/crashloopbackoff.md) |
| **128** | Invalid exit argument | Exit called with an out-of-range value | — |
| **137** | SIGKILL (128 + 9) | **OOMKilled**, a failed liveness probe, or a termination grace period that expired | [oomkilled.md](../../runbooks/pods/oomkilled.md) |
| **139** | SIGSEGV (128 + 11) | Segmentation fault — a native crash in the application or a library | [crashloopbackoff.md](../../runbooks/pods/crashloopbackoff.md) |
| **143** | SIGTERM (128 + 15) | Graceful shutdown. Usually **normal** during a rollout or scale-down | [rollout-rollback.md](../../runbooks/deployments/rollout-rollback.md) |
| **255** | Exit status out of range | Often a wrapper script returning `-1` | — |

Signals map to `128 + N`. Anything above 128 was killed by signal `code - 128`.

---

## The distinction that matters most: 137

**137 alone does not mean out of memory.** It means SIGKILL, and there are three
common senders:

| Sender | How to tell them apart |
| :--- | :--- |
| Kernel OOM killer | `lastState.terminated.reason` is `OOMKilled` |
| Failed liveness probe | `reason` is `Error`, plus `Unhealthy` events before the kill |
| Expired grace period | Occurs during shutdown, after a SIGTERM that was ignored |

```bash
kubectl get pod <pod> --namespace <namespace> \
  -o jsonpath='{.status.containerStatuses[*].lastState.terminated.reason}{"\n"}'
```

Treating every 137 as a memory problem leads to raising limits on a pod whose
liveness probe is simply too aggressive — the restarts continue, now with more
memory allocated.

---

## Exit code 0 on a service is a real failure

A web server that exits 0 has decided its work is done. With
`restartPolicy: Always` it restarts, exits again, and enters CrashLoopBackOff
while reporting *success* every time. Common causes: a config that puts it in a
one-shot mode, a missing foreground flag, or a shell script that runs the server
in the background and then returns.

---

## Where to read it

```bash
# Current and previous termination state
kubectl describe pod <pod> --namespace <namespace> | grep -A6 'Last State'

# Init containers report separately
kubectl get pod <pod> --namespace <namespace> \
  -o jsonpath='{range .status.initContainerStatuses[*]}{.name}{"\t"}{.lastState.terminated.exitCode}{"\n"}{end}'
```

---

## Related

- [pod-states.md](pod-states.md) — waiting and terminated reasons
- [event-reasons.md](event-reasons.md) — event REASON values
- [../../runbooks/triage.md](../../runbooks/triage.md)
