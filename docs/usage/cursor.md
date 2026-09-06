# Using `k8s-ai-troubleshooter` with Cursor

Cursor applies project rules automatically and can run terminal commands, which
makes it a full agentic client. The catch specific to Cursor: it is an *editor*,
so its instinct is to fix code. Kubernetes debugging is mostly about reading
cluster state, and the rules below exist to keep it from jumping to edits.

---

## 1. Setup

### Modern Cursor — `.cursor/rules/`

```bash
mkdir -p .cursor/rules
cp integrations/cursor/.cursorrules .cursor/rules/k8s-troubleshooting.mdc
```

Add frontmatter so the rule is always active:

```markdown
---
description: Kubernetes troubleshooting via k8s-ai-troubleshooter
alwaysApply: true
---
```

### Legacy Cursor — `.cursorrules`

```bash
cp integrations/cursor/.cursorrules ./.cursorrules
```

### Verify

```text
What safety tier is `kubectl scale deployment/api --replicas=0 --namespace prod`?
```

Expect **HUMAN_APPROVAL_REQUIRED** and a refusal to run it unprompted.

---

## 2. Recommended rule content

The shipped `.cursorrules` is short. For cluster work, extend it:

```markdown
---
description: Kubernetes troubleshooting via k8s-ai-troubleshooter
alwaysApply: true
---

# Kubernetes Troubleshooting

Start every Kubernetes investigation at runbooks/triage.md.
Route the observed signal through symptom-index.yaml before choosing a runbook.

## Safety tiers — enforced, not advisory
- SAFE_READ (get, describe, logs, top, helm list/status): run freely.
- HUMAN_APPROVAL_REQUIRED (apply, patch, scale, rollout, helm upgrade): propose,
  state blast radius, wait.
- DESTRUCTIVE (delete, helm uninstall, drain, --force): refuse unless I confirm
  explicitly in a separate message.

## Rules
- Never `kubectl delete pod` to "restart" something. It destroys the --previous
  logs that hold the answer.
- Never edit a manifest before diagnosing. The bug is usually in the cluster
  state, not the YAML in front of you.
- Quote real command output as evidence. Do not paraphrase it.
- Always give a confidence level, and say Low when the evidence is thin.
```

The "never edit a manifest before diagnosing" line is the important one in
Cursor specifically. Without it, a CrashLoopBackOff caused by a missing Service
turns into an unprompted rewrite of your Deployment YAML.

---

## 3. Worked example

> **You:** `@Terminal` the checkout service is down in staging

**Cursor:**

> ```bash
> kubectl get pods --namespace staging -l app=checkout
> ```
> ```text
> NAME                        READY   STATUS                       RESTARTS   AGE
> checkout-6b4c9d8f7-qr2mn    0/1     CreateContainerConfigError   0          4m
> ```
>
> `CreateContainerConfigError` routes via `symptom-index.yaml` to
> `runbooks/storage/mount-failure.md` — this state usually means a referenced
> ConfigMap or Secret is absent.
>
> ```bash
> kubectl describe pod checkout-6b4c9d8f7-qr2mn --namespace staging
> ```
> ```text
> Warning  Failed  Error: secret "checkout-stripe-key" not found
> ```
> ```bash
> kubectl get secrets --namespace staging
> ```
> ```text
> NAME                     TYPE     DATA   AGE
> checkout-db-credentials  Opaque   2      31d
> ```
>
> ## Likely Root Cause
> The Deployment mounts a Secret named `checkout-stripe-key` which does not exist
> in `staging`. It exists in `prod` — this looks like a manifest promoted without
> its Secret.
>
> ## Confidence Level
> **High.** The kubelet names the missing object exactly.
>
> ## Recommended Remediation
> Create the Secret in `staging`. I can show you the command, but I will not run
> it — creating a Secret means handling its value, and that should not pass
> through me.
>
> ## Human Approval Required
> Creating a Secret is `HUMAN_APPROVAL_REQUIRED`. Run it yourself so the key
> never enters this conversation.

Note it declined to handle the secret value even though it could have. That is
worth keeping in your rules.

---

## 4. Add the MCP server

Cursor supports MCP. Wiring it up gives deterministic runbook lookup and safety
classification as tool calls — see [mcp.md](mcp.md) for `.cursor/mcp.json`.

---

## 5. Troubleshooting

| Symptom | Cause | Fix |
| :--- | :--- | :--- |
| Rules ignored | `alwaysApply` not set | Add the frontmatter block |
| Edits YAML instead of diagnosing | Missing the "diagnose first" rule | Add the §2 rules |
| Will not run kubectl | Terminal access off | Enable it, or paste output manually |
| Ignores runbooks | Repo not in workspace | Open the repo, or use absolute paths in rules |

---

## Related

- [README.md](README.md) — other platforms
- [mcp.md](mcp.md)
- [../../integrations/cursor/.cursorrules](../../integrations/cursor/.cursorrules)
