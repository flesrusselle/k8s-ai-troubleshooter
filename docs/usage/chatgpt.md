# Using `k8s-ai-troubleshooter` with ChatGPT

ChatGPT in a browser cannot reach your cluster. That is not a limitation to work
around — it is the safest mode this project supports, because nothing the model
says can touch production. You bring the evidence; it does the analysis.

The tradeoff is that **you** are the one pasting cluster output into a hosted
service, so redaction stops being optional.

---

## 1. Setup — a Project or Custom GPT

### Option A — Project instructions (recommended)

Create a Project called *Kubernetes Troubleshooting* and paste
`integrations/chatgpt/instructions.md` into its instructions. Every chat in the
project inherits them.

### Option B — Custom GPT

Create a GPT, paste the same instructions, and **upload as knowledge files**:

- `symptom-index.yaml`
- the runbooks you care about (or a zip of `runbooks/`)
- `docs/safety-model.md`

Uploading the runbooks is what makes a Custom GPT worth the setup over a plain
chat — it can then quote the actual runbook instead of recalling Kubernetes
trivia.

### Option C — one-off chat

Paste `integrations/generic/system-prompt.md` as your first message. Works, but
you repeat it every conversation.

---

## 2. Redact before you paste — every time

This is the step people skip.

```bash
# Collect everything, redacted, in one command
python3 scripts/collect.py --namespace prod --output evidence-bundle

# Or filter a single command's output
kubectl describe pod api-7d9f --namespace prod | python3 scripts/redact.py
```

`kubectl describe pod` prints **every environment variable value**. If your app
takes `DB_PASSWORD` from a Secret, describing the pod prints the password. Paste
that into a hosted chat and it is disclosed — assume it must be rotated.

With redaction the diagnosis survives intact:

```text
DB_PASSWORD:   [REDACTED:key-value:f52fbd32]
DATABASE_URL:  postgres://app:[REDACTED:url-credentials:eb67b43f]@db.prod:5432/main
LOG_LEVEL:     debug
```

You can still see the variable is set, which database it targets, and the log
level. See [evidence-bundles.md](../evidence-bundles.md).

You can upload the whole `evidence-bundle/` directory to a chat — the files are
already redacted.

---

## 3. Worked example

**You:**

```text
Kubernetes issue. Follow the k8s-ai-troubleshooter method: start with triage
scope, route the signal, then give me root cause with a confidence level.
Do not give me a fix to run until you have stated the blast radius.

$ kubectl get pods --namespace prod
NAME                        READY   STATUS             RESTARTS      AGE
payments-api-7d9f4b-x2kql   0/1     CrashLoopBackOff   9 (30s ago)   14m
payments-api-7d9f4b-mm81z   1/1     Running            0             3d

$ kubectl describe pod payments-api-7d9f4b-x2kql --namespace prod
    Last State:     Terminated
      Reason:       Error
      Exit Code:    1
    Environment:
      DATABASE_HOST:  [REDACTED:key-value:a91f2c30]
      LOG_LEVEL:      info

$ kubectl logs payments-api-7d9f4b-x2kql --namespace prod --previous
FATAL could not connect to database:
  dial tcp: lookup postgres-primary.prod.svc.cluster.local: no such host
```

**ChatGPT (correctly configured):**

> ## Situation
> One of two `payments-api` replicas is in CrashLoopBackOff; the other is
> healthy. Scope is a single workload, not a node or cluster fault.
>
> ## Evidence
> - Exit code 1 — application-level failure, not OOM (137) or missing binary (127).
> - `--previous` logs: DNS lookup for `postgres-primary.prod.svc.cluster.local` fails.
> - One replica healthy, which is unusual for a config error and worth explaining.
>
> ## Likely Root Cause
> The Service name `postgres-primary` does not resolve. Either it was renamed or
> it lives in another namespace.
>
> ## Confidence Level
> **Medium.** The DNS failure is unambiguous, but I cannot see your Services, and
> the healthy replica is unexplained — it may be running an older spec that has
> not been rescheduled yet.
>
> ## What Would Raise This to High
> ```bash
> kubectl get svc --namespace prod | grep postgres
> kubectl get pods --namespace prod -o custom-columns='POD:.metadata.name,IMAGE:.spec.containers[0].image'
> ```
>
> ## Recommended Remediation
> If the Service is named differently, update `DATABASE_HOST` on the Deployment.
>
> ## Human Approval Required
> `HUMAN_APPROVAL_REQUIRED` — restarts every replica. Blast radius: both
> `payments-api` pods, brief 502s during rollout. Run it yourself; I cannot.

Note it gave **Medium** and named what would raise it, rather than asserting a
confident answer from partial evidence. That is the behavior you want.

---

## 4. Prompts that work

```text
Route this signal using the k8s-ai-troubleshooter symptom index, then tell me
which runbook applies and why:  FailedMount

I pasted output above. Do not guess beyond it — tell me exactly which command
would settle the ambiguity.

Give me the SAFE_READ commands to run next, one per line, nothing that mutates.

Rate your confidence and justify the rating against the evidence I gave you.
```

---

## 5. Limits

- **No cluster access.** It cannot verify anything you did not paste. Treat every
  answer as a hypothesis until you check it.
- **Stale knowledge.** Kubernetes changes; the runbooks in this repo are the
  source of truth over the model's recollection. Upload them.
- **Context limits.** Do not paste a 10,000-line log. Paste the last 100 lines
  plus the `describe` output, which is where the answer usually is.
- **It cannot enforce safety tiers.** Nothing stops it suggesting
  `kubectl delete`. You are the gate. That is why the response schema requires it
  to state blast radius before proposing a fix.

---

## Related

- [README.md](README.md) — other platforms
- [../evidence-bundles.md](../evidence-bundles.md) — redaction, in detail
- [../../integrations/chatgpt/instructions.md](../../integrations/chatgpt/instructions.md)
