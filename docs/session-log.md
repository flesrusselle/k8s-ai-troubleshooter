# Session Log

Every other tool in this project answers "what should happen right now."
Nothing answered "what happened last time" — until this. The session log is
an append-only, local JSONL file that records a diagnosis or a collection run,
so a recurring incident becomes visible instead of starting from zero every
time someone opens a new conversation.

This is deliberately not a database, a metrics pipeline, or a dashboard. It is
the smallest thing that makes "have we seen this before?" answerable, and the
foundation a future confidence-calibration check — comparing what an assistant
declared against what actually happened — would build on.

---

## What gets logged, and by what

| Source | Written by | What it records |
| :--- | :--- | :--- |
| `collect` | `scripts/collect.py`, automatically, every run | scope, unhealthy pod count, redaction summary, bundle path |
| `mcp` | The `log_diagnosis` MCP tool, called by an assistant | signal, routed runbook, confidence, root cause, notes |

`collect` entries happen without anyone asking — they're a side effect of
gathering evidence. `mcp` entries require an assistant to *decide* to log a
conclusion, which is why every [usage guide](usage/README.md) should tell it to.

---

## Where it lives

```text
1. $K8S_AI_TROUBLESHOOTER_SESSION_LOG   — set this for a shared/team location
2. ./.k8s-ai-troubleshooter/sessions.jsonl  — default, relative to cwd
```

The default is git-ignored and machine-local. For a team, point the
environment variable at a location everyone's tooling shares — a mounted
volume, a synced directory, or (if you're comfortable with the write
contention) a location in shared storage. This project does not ship a shared
backend; it ships the file format and the two writers above.

---

## Reading it back

```bash
# Counts by runbook, confidence, and source — the default view
python3 scripts/session_log.py

# The raw JSON, most recent last
python3 scripts/session_log.py --tail 20

# Where is it actually writing to?
python3 scripts/session_log.py --path
```

```text
14 session(s) recorded.

By runbook:
   5  runbooks/pods/oomkilled.md
   3  runbooks/networking/service-unreachable.md
   2  runbooks/storage/pvc-pending.md
   ...

By confidence:
  10  High
   3  Medium
   1  Low

By source:
   9  mcp
   5  collect

Recurring (3+ times) — worth investigating the pattern, not just the instance:
  - runbooks/pods/oomkilled.md
```

That last section is the point. Five OOMKilled sessions this month against
one workload is not five separate incidents — it's one undersized memory limit
that keeps getting patched around instead of fixed. The session log is what
makes that visible; nothing else in this project would have told you.

---

## Calling `log_diagnosis`

Any MCP client (see [usage/mcp.md](usage/mcp.md)) can call this once a session
reaches a conclusion:

```json
{
  "name": "log_diagnosis",
  "arguments": {
    "signal": "OOMKilled",
    "runbook": "runbooks/pods/oomkilled.md",
    "confidence": "High",
    "root_cause": "memory limit set to 128Mi, steady-state usage is 340Mi",
    "evidence_bundle": "/home/user/evidence-bundle",
    "notes": "raised limit to 512Mi, verified stable for 20 minutes"
  }
}
```

`confidence` must be exactly `"High"`, `"Medium"`, or `"Low"` — anything else
is rejected, not written. A log where one entry says `"High"` and another says
`"Certain"` or `"90%"` can't be grouped by `--summary`, which defeats the
reason this exists. This is enforced in code
(`integrations/mcp/server.py::log_diagnosis`), not left as a convention for the
model to maybe follow.

**Call it once per session, at the end** — not once per command, and not for a
session that never got past collecting evidence. A log entry per `kubectl get`
would be noise; a log entry per conclusion is a record.

---

## What this is not

- **Not a replacement for the evidence bundle.** The bundle has the actual
  command output; the log has a pointer to it (`evidence_bundle`) plus the
  conclusion. Old bundles can be deleted once resolved — the log entry
  referencing a since-deleted path is still useful as a historical record.
- **Not confidence calibration, yet.** Nothing currently checks whether a
  "High confidence" entry turned out to be right. That requires closing the
  loop — recording an outcome after the fact — which this project doesn't do
  today. The log is the prerequisite for that, not the feature itself.
- **Not multi-writer safe under heavy concurrency.** Appends are simple file
  writes; two processes writing at the exact same instant could interleave.
  For the expected usage pattern — one assistant, occasionally — this is not
  a practical problem. A shared team backend with real concurrency guarantees
  would need more than a JSONL file.

---

## Related

- [../scripts/session_log.py](../scripts/session_log.py)
- [usage/mcp.md](usage/mcp.md) — the `log_diagnosis` tool in context
- [evidence-bundles.md](evidence-bundles.md) — what `collect` entries point at
