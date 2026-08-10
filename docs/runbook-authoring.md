# Runbook Authoring Guide

Every runbook in `k8s-ai-troubleshooter` must follow a standard Markdown structure:

---

## 📝 Required Runbook Template

```markdown
# [Runbook Title]

## Purpose
Brief summary of what issue this runbook diagnoses.

## When to Use
Symptoms or triggers when this runbook should be executed.

## Safety Level
`SAFE_READ` | `SAFE_DIAGNOSTIC` | `HUMAN_APPROVAL_REQUIRED` | `DESTRUCTIVE`

## Symptoms
- List of observable symptoms.

## Quick Diagnosis
Fast command sequence to verify the issue.

## Detailed Investigation
Step-by-step diagnostic traversal.

## Decision Tree
Reference to corresponding decision tree file.

## Evidence to Collect
Exact fields, logs, or events to gather.

## Root Cause Patterns
Table or list of observed patterns mapped to root causes and confidence levels.

## Confirmation
How to verify the diagnosis before proposing fixes.

## Remediation
Explanation of remediation steps.

## Human Approval Required
Explicit list of commands that require human consent before execution.

## Related Runbooks
Links to related diagnostic runbooks.

## Official Documentation
Official Kubernetes or Helm documentation links.
```

---

## Blast Radius, Verification & Rollback

Three sections every runbook must carry. They exist because a runbook that ends
at "run this command" hands the operator the risky half of the job and keeps the
easy half.

### `## Blast Radius`

What the remediation affects, and for how long — stated **before** approval is
requested, so the decision is made with the cost in view.

Answer three questions: which workloads are touched beyond the one being fixed;
how long the disruption lasts; and what shared state changes. "Restarts the pod"
is not a blast radius. "Replaces every pod in the Deployment; ~15s of 502s during
rollout; the ConfigMap change also affects the two other workloads mounting it"
is.

For a read-only runbook, say so and say why, e.g. *"None — every command here is
read-only. Remediation reached through routing inherits the approval
requirements of its own runbook."*

### `## Verification`

Observable evidence that the fix worked. A command plus the specific output that
constitutes success.

The trap is verifying too early or too narrowly. State what would be a *false*
pass:

- a pod that survives 30 seconds when it previously crashed in 2 has not
  necessarily recovered — compare against the old lifetime, not against zero;
- one successful request through a Service with three backends can hit the
  healthy one;
- a memory limit that holds at 3am proves nothing about peak.

### `## Rollback`

How to undo it, **and what cannot be undone**. The second half is the valuable
one. Say plainly when a remediation is one-way:

- deleted PVCs with `reclaimPolicy: Delete` destroy their data;
- objects admitted while a webhook was disabled were never validated;
- a rollback does not reverse a database migration;
- a released load balancer usually does not return with the same IP.

Do not distinguish `## Confirmation` from `## Verification` by accident:
**Confirmation** checks the *root cause* before acting; **Verification** checks
the *fix* afterwards.

---

## Reference tables

When a runbook mentions an exit code, a pod state, or an event reason, link to
[`docs/reference/`](reference/README.md) rather than restating the table. The
tables are maintained in one place and route to runbooks themselves.
