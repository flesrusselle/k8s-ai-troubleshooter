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
