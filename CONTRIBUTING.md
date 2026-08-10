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
- [ ] **Blast Radius**: what the remediation affects and for how long, stated before the approval gate.
- [ ] **Verification**: observable evidence the fix worked, including what would count as a false pass.
- [ ] **Rollback**: how to undo it, and what specifically cannot be undone.
- [ ] Added to `symptom-index.yaml` with at least one signal — an unrouted runbook fails CI.
- [ ] Official documentation links (Kubernetes / Helm docs). No dead links.
- [ ] Validated against `schemas/runbook.schema.json`.

See `docs/runbook-authoring.md` for what distinguishes Blast Radius/Verification/
Rollback from the existing Confirmation section, and for common mistakes.

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

If your change touches `scripts/collect.py`, `symptom-index.yaml`, or a
runbook's Quick Diagnosis commands, also run the integration suite against a
real cluster. It induces actual failures (CrashLoopBackOff, a tainted node, an
unbound PVC) and checks the real signal Kubernetes emits routes correctly —
the offline suite above only proves the matching logic is correct against
strings chosen by hand.

```bash
# Requires kind + a running Docker daemon. Creates and destroys its own
# disposable cluster; never touches an existing one.
./scripts/integration/run_kind_tests.sh
```

This also runs in CI as a separate `kind-integration-tests` job.

---

## 🚀 Pull Request Guidelines & Release Preview

* Target the `main` branch.
* Ensure all GitHub Actions pass.
* Every PR automatically generates a **Release Preview** in the PR description, including git diff metrics, updated runbooks, security impact, and `Asia/Manila` (`PHT`) timestamps.
