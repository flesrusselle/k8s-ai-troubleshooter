# Job & CronJob Failure Runbook

## Purpose
Diagnose Jobs that fail, never complete, or leave pods behind, and CronJobs that
do not fire, fire too often, or silently stop scheduling.

## When to Use
A Job reports `BackoffLimitExceeded` or `DeadlineExceeded`, a CronJob has not
run when expected, or completed Job pods are accumulating.

## Safety Level
`SAFE_READ`

## Symptoms
- `Job has reached the specified backoff limit`.
- CronJob `LAST SCHEDULE` shows `<none>` or a stale timestamp.
- Hundreds of `Completed` or `Error` pods in a namespace.
- A Job that reports `1/1` completions but whose work never happened.

## Quick Diagnosis

Job pods are deleted on cleanup, taking their logs with them. Capture logs
*before* investigating anything else.

```bash
# 1. Job state
kubectl get jobs -n <namespace>
kubectl describe job <job-name> -n <namespace>

# 2. Logs from the Job's pods — get these first
kubectl logs -n <namespace> -l job-name=<job-name> --tail=200 --all-containers

# 3. CronJob schedule state
kubectl get cronjob <name> -n <namespace> \
  -o custom-columns='NAME:.metadata.name,SCHEDULE:.spec.schedule,SUSPEND:.spec.suspend,ACTIVE:.status.active,LAST:.status.lastScheduleTime'

# 4. Pods left behind
kubectl get pods -n <namespace> --field-selector=status.phase=Failed
```

## Detailed Investigation

```text
Job / CronJob problem
       ↓
Job exists?
       ↓ no  → CronJob never created it
       │        suspend: true? schedule wrong? controller stopped?
       ↓ yes
Job completed?
       ↓ no  → BackoffLimitExceeded  → the pod is failing; read its logs
       │       DeadlineExceeded      → activeDeadlineSeconds hit; work too slow
       ↓ yes
Did the work actually happen?
       → exit 0 does not mean success if the script swallows errors
```

1. **`backoffLimit` counts pod failures, not retries of a step.** The default is
   6, with exponential backoff capped at 6 minutes. A Job that fails fast can
   exhaust it in under a minute; a slow one can take half an hour.
2. **`suspend: true` is silent.** A suspended CronJob produces no events, no
   pods, and no errors. It simply never runs. Check it first when a CronJob has
   "stopped working".
3. **Missed schedules are permanent.** If the controller cannot start a job
   within `startingDeadlineSeconds`, that occurrence is skipped and never
   retried. More than 100 missed schedules and the controller stops scheduling
   entirely, which is why a CronJob can die after a long control-plane outage.
4. **`concurrencyPolicy` explains both duplicates and gaps.** `Allow` (default)
   permits overlapping runs, so a job slower than its interval piles up.
   `Forbid` skips the new run; `Replace` kills the old one mid-work.
5. **Cron is evaluated in the controller's timezone** unless `spec.timeZone` is
   set. A job scheduled for local midnight may run at a different wall-clock hour
   than you expect.

## Decision Tree
`decision-trees/pod-failure.yaml` once a Job pod is identified as failing.

## Evidence to Collect
- `.status` of the Job: `succeeded`, `failed`, `active`, and conditions.
- Logs of the failing pod, before cleanup removes it.
- `backoffLimit`, `activeDeadlineSeconds`, `ttlSecondsAfterFinished`.
- For CronJobs: `schedule`, `suspend`, `concurrencyPolicy`,
  `startingDeadlineSeconds`, `timeZone`, `lastScheduleTime`.
- Whether the failing pod was OOMKilled or evicted rather than exiting non-zero.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| `BackoffLimitExceeded`, pod exit 1 | Application error in the job — read the pod logs | High |
| `DeadlineExceeded` | `activeDeadlineSeconds` shorter than real runtime | High |
| CronJob `LAST SCHEDULE <none>`, no pods | `suspend: true`, or an invalid schedule | High |
| CronJob stopped after an outage | >100 missed schedules; controller gave up | Medium |
| Overlapping runs corrupting state | `concurrencyPolicy: Allow` with a job slower than its interval | High |
| Pods accumulating forever | No `ttlSecondsAfterFinished`, no history limits | High |
| Job pod OOMKilled | Memory limit too low — see the OOMKilled runbook | High |
| Job reports success, work not done | Script does not propagate the failing exit code | Medium |

## Confirmation
Confirm a suspected schedule or image problem by running the Job manually,
outside the schedule:

```bash
kubectl create job --from=cronjob/<cronjob-name> <name>-manual -n <namespace>
kubectl logs -n <namespace> -l job-name=<name>-manual --follow
```

If the manual run succeeds, the fault is in scheduling — suspension, cron
expression, or timezone. If it fails identically, the fault is in the job itself.

## Remediation
Fix the application error, raise `backoffLimit` or `activeDeadlineSeconds` to
match real runtime, unsuspend the CronJob, correct the cron expression, or set
`concurrencyPolicy: Forbid` for jobs that must not overlap. Set
`ttlSecondsAfterFinished` to stop pod accumulation.

## Blast Radius
Manually triggering a Job runs real work — it may write to databases, send
messages, or charge money. Deleting a Job removes its history and its pods,
taking the logs with them. Unsuspending a CronJob can trigger catch-up runs.

## Human Approval Required
- `kubectl create job --from=cronjob/<name> <name>-manual -n <namespace>` — runs real work
- `kubectl patch cronjob <name> -n <ns> -p '{"spec":{"suspend":false}}'`
- `kubectl delete job <name> -n <namespace>` — **DESTRUCTIVE**, discards job history

## Verification
```bash
kubectl get jobs -n <namespace>
kubectl logs -n <namespace> -l job-name=<job-name> --tail=50
```
Verified when the Job reports `COMPLETIONS 1/1` and its logs show the work
actually finished. Exit code 0 is not sufficient: a script that swallows errors
reports success while doing nothing.

## Rollback
A Job that has run cannot be un-run. Re-suspending a CronJob stops future
occurrences but does not stop one already in flight — delete the active Job for
that.

## Related Runbooks
- [../pods/crashloopbackoff.md](../pods/crashloopbackoff.md)
- [../pods/oomkilled.md](../pods/oomkilled.md)
- [../pods/pending.md](../pods/pending.md)
- [../scheduling/resourcequota.md](../scheduling/resourcequota.md)

## Official Documentation
- [Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/)
- [CronJob](https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/)
