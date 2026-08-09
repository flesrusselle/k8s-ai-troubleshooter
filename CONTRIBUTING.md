# Contributing to `k8s-ai-troubleshooter`

Thank you for helping build an AI-readable, open-source Kubernetes diagnostic system!

---

## 📐 Runbook Quality Gate

Every proposed runbook must satisfy the following checks:

- [ ] Clear purpose and symptom list.
- [ ] Explicit safety classification (`SAFE_READ`, `SAFE_DIAGNOSTIC`, `HUMAN_APPROVAL_REQUIRED`, `DESTRUCTIVE`).
- [ ] Safe diagnostic `kubectl` / `helm` commands using exact, tested JSONPath/output flags.
- [ ] Structured decision tree reference or steps.
- [ ] Root cause patterns with evidence indicators.
- [ ] Clear separation between **DIAGNOSIS** (read-only) and **REMEDIATION** (human approval required).
- [ ] Official documentation links (Kubernetes / Helm docs). No dead links.
- [ ] Validated against `schemas/runbook.schema.json`.

---

## 🛡️ AI Safety Quality Gate

All integrations and runbooks must enforce:

1. **Read-Only Default**: Never automatically issue state-modifying or destructive commands.
2. **Human Approval**: Any `rollout restart`, `scale`, `patch`, `apply`, `delete`, `helm upgrade`, or `helm rollback` must explicitly state `HUMAN APPROVAL REQUIRED`.
3. **No Hallucinated Evidence**: AI assistants must distinguish between observed command output, unverified hypotheses, and unknown states.

---

## 🧪 Local Testing & Validation

Run the test suite and validation scripts before submitting a Pull Request:

```bash
# 1. Run offline python test suite
python3 -m unittest discover tests

# 2. Run structural validation script
python3 scripts/validate.py
```

---

## 🚀 Pull Request Guidelines & Release Preview

* Target the `main` branch.
* Ensure all GitHub Actions pass.
* Every PR automatically generates a **Release Preview** in the PR description, including git diff metrics, updated runbooks, security impact, and `Asia/Manila` (`PHT`) timestamps.
