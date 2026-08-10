# How to Use `k8s-ai-troubleshooter`

Detailed, platform-specific setup and worked examples.

---

## Pick your mode first

The right setup depends on one question: **can the assistant run commands
against your cluster?**

```text
Can the assistant execute kubectl itself?
│
├── Yes, it has terminal access
│   └── Mode 3 — Agentic
│       Claude Code, Antigravity, Cursor, MCP clients
│       The assistant runs SAFE_READ commands directly and stops
│       at the approval gate.
│
├── No, it is a browser chat
│   └── Mode 2 — Bundle
│       ChatGPT, Claude.ai, Gemini, any web LLM
│       You collect a redacted bundle, paste or upload it, and the
│       assistant analyses it offline.
│
└── There is no assistant
    └── Mode 1 — Manual
        Use the runbooks yourself as an SRE reference.
```

| Platform | Guide | Mode |
| :--- | :--- | :--- |
| Claude Code | [claude-code.md](claude-code.md) | Agentic |
| Antigravity | [antigravity.md](antigravity.md) | Agentic |
| Cursor | [cursor.md](cursor.md) | Agentic |
| MCP clients | [mcp.md](mcp.md) | Agentic |
| ChatGPT | [chatgpt.md](chatgpt.md) | Bundle |
| GitHub Copilot | [copilot.md](copilot.md) | Agentic / in-editor |
| Any other LLM | [generic-llm.md](generic-llm.md) | Bundle |

---

## The shape of every session

Regardless of platform, a correct session follows the same six beats. If your
assistant skips one, the integration is not loaded properly.

```text
1. SCOPE      → runbooks/triage.md
                 How big is this? One pod, one node, or the cluster?

2. ROUTE      → symptom-index.yaml
                 Match the literal signal (CrashLoopBackOff, FailedMount,
                 exit code 137) to a runbook.

3. COLLECT    → the runbook's Quick Diagnosis commands
                 SAFE_READ only. No mutations, no exceptions.

4. CONCLUDE   → the runbook's Root Cause Patterns table
                 State a root cause WITH a confidence level and the
                 evidence that supports it.

5. GATE       → the runbook's Human Approval Required section
                 Propose the fix. Do not run it. Wait.

6. LOG        → the log_diagnosis MCP tool, if available
                 Record the conclusion once, at the end. See
                 docs/session-log.md — this is what makes a recurring
                 incident visible instead of investigated from zero
                 every time.
```

---

## What "correct behavior" looks like

Use this to judge whether your integration is actually working.

**The assistant should:**

- Run `kubectl get`, `describe`, `logs`, `top`, `helm list` without asking.
- Name the runbook it is following.
- Quote real output as evidence rather than describing it.
- Give a confidence level, and say "Low" when the evidence is thin.
- Stop before `rollout restart`, `scale`, `apply`, `patch`, `helm upgrade`.
- Refuse `delete`, `helm uninstall`, and `--force` outright without an explicit,
  separate confirmation.

**The assistant should not:**

- Suggest `kubectl delete pod` as a first move. Deleting a crashing pod destroys
  the `--previous` logs that contain the answer.
- Guess a root cause before reading logs.
- Run a mutating command because it "seemed implied".
- Claim a fix worked without verifying.

If your assistant deletes a pod to "restart" it, the integration is not loaded.
Say so and point it back at [safety-model.md](../safety-model.md).

---

## Redaction applies to every mode

Whatever platform you use, cluster output contains credentials. Before pasting
anything into a hosted assistant:

```bash
kubectl describe pod api-7d9f -n prod | python3 ../scripts/redact.py
```

Or collect everything at once:

```bash
python3 scripts/collect.py -n prod -o evidence-bundle
```

See [evidence-bundles.md](../evidence-bundles.md). This matters most in Mode 2,
where you are pasting by hand, but it applies to agentic modes too — the
assistant's context window ends up wherever that provider stores it.

---

## Related

- [safety-model.md](../safety-model.md) — the four tiers and what gates each
- [ai-integration.md](../ai-integration.md) — the mandatory response schema
- [evidence-bundles.md](../evidence-bundles.md) — redaction and collection
- [session-log.md](../session-log.md) — recording a conclusion, and reading it back
- [reference/](../reference/README.md) — exit codes, pod states, event reasons
- [../../runbooks/triage.md](../../runbooks/triage.md) — where a session starts
