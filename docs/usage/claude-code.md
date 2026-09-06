# Using `k8s-ai-troubleshooter` with Claude Code

Claude Code is a terminal-based agent, so it can run `kubectl` itself. That
makes it the most capable mode — and the one where the safety tiers matter most,
because the assistant is one approval away from changing your cluster.

---

## 1. Setup

### Option A — clone into your working directory (recommended)

Claude Code automatically reads a `CLAUDE.md` from the directory it starts in.

```bash
git clone https://github.com/flesrusselle/k8s-ai-troubleshooter.git
cd k8s-ai-troubleshooter
cp integrations/claude/CLAUDE.md ./CLAUDE.md
claude
```

### Option B — reference it from an existing project

If you already have a `CLAUDE.md` in your infrastructure repo, add a pointer
rather than copying the rules, so updates flow through:

```markdown
## Kubernetes Troubleshooting

When debugging Kubernetes, follow ~/tools/k8s-ai-troubleshooter/integrations/claude/CLAUDE.md.
Start every investigation at runbooks/triage.md and route via symptom-index.yaml.
Never run a command above SAFE_DIAGNOSTIC without explicit approval.
```

### Option C — user-level, applies to every project

Append the same block to `~/.claude/CLAUDE.md`. Use this if you debug clusters
from many different repositories.

### Verify the setup

Ask Claude directly:

```text
What safety tier does `kubectl delete pod web-1 --namespace prod --force` fall into,
and which runbook covers CrashLoopBackOff?
```

A correctly configured session answers **DESTRUCTIVE** and
`runbooks/pods/crashloopbackoff.md`. If it does not, the `CLAUDE.md` was not
picked up — check you launched `claude` from the right directory, and run
`/memory` to see which files were loaded.

---

## 2. Permissions

Claude Code asks before running commands. For read-only Kubernetes work, that
gets tedious fast. Pre-approve the safe tier and nothing else.

Add to `.claude/settings.json` in your project:

```json
{
  "permissions": {
    "allow": [
      "Bash(kubectl get:*)",
      "Bash(kubectl describe:*)",
      "Bash(kubectl logs:*)",
      "Bash(kubectl top:*)",
      "Bash(kubectl explain:*)",
      "Bash(kubectl api-resources:*)",
      "Bash(kubectl cluster-info)",
      "Bash(kubectl version:*)",
      "Bash(helm list:*)",
      "Bash(helm status:*)",
      "Bash(helm get:*)",
      "Bash(helm history:*)",
      "Bash(python3 scripts/collect.py:*)",
      "Bash(python3 scripts/redact.py:*)"
    ],
    "deny": [
      "Bash(kubectl delete:*)",
      "Bash(kubectl drain:*)",
      "Bash(helm uninstall:*)",
      "Bash(helm rollback:*)"
    ]
  }
}
```

**Why an explicit `deny` list when the instructions already forbid these:**
instructions are followed by a model, `deny` is enforced by the harness. Keep
both. The `deny` entries are the ones you cannot afford to have talked around.

Note what is *absent* from `allow`: `kubectl apply`, `patch`, `scale`,
`rollout`, `helm upgrade`. Those stay promptable on purpose — you want to be
asked.

Do not use `--dangerously-skip-permissions` for cluster work.

---

## 3. Worked example — a real CrashLoopBackOff session

> **You:** The payments API is throwing 502s in prod. Figure out why.

**Claude — step 1, scope.** Following `runbooks/triage.md`:

```bash
kubectl get pods --namespace prod --field-selector=status.phase!=Running
```
```text
NAME                        READY   STATUS             RESTARTS      AGE
payments-api-7d9f4b-x2kql   0/1     CrashLoopBackOff   9 (30s ago)   14m
```

> One pod, one namespace. Workload-scoped, not a node or cluster fault.
> `CrashLoopBackOff` routes via `symptom-index.yaml` to
> `runbooks/pods/crashloopbackoff.md`.

**Step 2, exit code.**

```bash
kubectl describe pod payments-api-7d9f4b-x2kql --namespace prod
```
```text
    Last State:     Terminated
      Reason:       Error
      Exit Code:    1
      Started:      Mon, 10 Aug 2026 09:14:01 +0800
      Finished:     Mon, 10 Aug 2026 09:14:03 +0800
```

> Exit code 1 is an application-level crash, not OOM. Per the runbook, exit 137
> would have routed to `oomkilled.md` instead. Two seconds from start to finish
> means it fails during initialization.

**Step 3, the logs that matter.**

```bash
kubectl logs payments-api-7d9f4b-x2kql --namespace prod --previous --all-containers
```
```text
2026-08-10T01:14:03Z FATAL could not connect to database:
  dial tcp: lookup postgres-primary.prod.svc.cluster.local: no such host
```

**Step 4, conclusion.**

> ## Likely Root Cause
> The pod cannot resolve `postgres-primary.prod.svc.cluster.local`. The Service
> does not exist under that name — `kubectl get svc --namespace prod` lists
> `postgres-primary-rw`, renamed by the operator upgrade 20 minutes before the
> first crash.
>
> ## Confidence Level
> **High.** The DNS name in the error does not exist; the name that does exist
> differs; the timeline matches the operator upgrade.
>
> ## Recommended Remediation
> Update `DATABASE_HOST` in the `payments-api` Deployment to
> `postgres-primary-rw.prod.svc.cluster.local`.
>
> ## Human Approval Required
> This is `HUMAN_APPROVAL_REQUIRED` — it restarts every pod in the Deployment.
> Blast radius: all 3 payments-api replicas, ~15s of 502s during rollout.
> Shall I proceed?

**Note what did not happen.** Claude did not delete the pod to "restart it" —
that would have destroyed the `--previous` logs holding the answer. It did not
run `kubectl set env` unprompted. It stopped at the gate.

---

## 4. Using an evidence bundle instead

For a large or unfamiliar cluster, collect once rather than command-by-command:

```bash
python3 scripts/collect.py --namespace prod --output evidence-bundle
```

```text
Analyse ./evidence-bundle. Start at runbooks/triage.md, route via
symptom-index.yaml, and give me a ranked list of what is broken with
a confidence level for each.
```

This is faster on wide problems ("something is wrong in prod") because Claude
reads 25 files in one pass instead of spending a turn per command. It is also
the only safe way to share cluster state into a conversation you might export.

---

## 5. Useful prompts

```text
Follow runbooks/triage.md and tell me the blast radius before anything else.

Route this with symptom-index.yaml — do not guess which runbook applies:
  <paste the STATUS or event REASON>

Classify every command you are about to run using scripts/safety.py first.

Explain why you ruled out OOMKilled, citing the evidence.

I have approved the fix. Run it, then verify with the runbook's
Confirmation section and show me the output.
```

---

## 6. Troubleshooting the integration

| Symptom | Cause | Fix |
| :--- | :--- | :--- |
| Claude ignores the runbooks | `CLAUDE.md` not loaded | Run `/memory` to list loaded files; relaunch from the repo root |
| Prompts on every `kubectl get` | No `allow` rules | Add the `permissions.allow` block above |
| Claude suggests `kubectl delete pod` | Instructions not applied | Point it at `docs/safety-model.md`; verify with the tier question in §1 |
| Claude runs a fix without asking | Missing `deny` rules | Add the `deny` block — enforcement beats instruction |
| Claude cannot find the runbooks | Wrong working directory | `pwd` should be the repo root, or use absolute paths in `CLAUDE.md` |
| Answers ignore the response schema | Schema not read | Reference `docs/ai-integration.md` explicitly in your prompt |

---

## 7. Limits

- Claude sees only what it runs. It cannot see your cloud console, your CNI's
  internal state, or a node you have not given it access to.
- `kubectl` runs as **you**. RBAC applies to the assistant exactly as it applies
  to your kubeconfig — this project adds no privileges and removes none.
- A confident wrong answer is still possible. The Confirmation section of each
  runbook exists precisely to check the hypothesis before you act on it.
- Redaction is best effort. Review before exporting a conversation.

---

## Related

- [../safety-model.md](../safety-model.md)
- [../evidence-bundles.md](../evidence-bundles.md)
- [../../integrations/claude/CLAUDE.md](../../integrations/claude/CLAUDE.md)
- [README.md](README.md) — other platforms
