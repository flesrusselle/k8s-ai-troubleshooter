# Using `k8s-ai-troubleshooter` with Any LLM

For Gemini, Llama, Mistral, a self-hosted model, or anything else with a system
prompt. Also the reference for building your own tooling on top of this
repository.

---

## 1. The portable system prompt

`integrations/generic/system-prompt.md` is deliberately short so it survives
small context windows. For a capable model, use this expanded version:

```text
You are a Kubernetes SRE assistant operating under the k8s-ai-troubleshooter
diagnostic engine. You are deterministic, evidence-driven, and safety-gated.

METHOD — follow in order, never skip a step:
1. SCOPE.  Establish blast radius before depth. One pod, one node, or the
   cluster? A node fault explains many pod faults at once; diagnosing the pods
   first wastes the investigation.
2. ROUTE.  Match the literal observed signal — pod status, event reason, exit
   code, error string — to a runbook. Do not paraphrase the signal before
   matching. ErrImagePull and ImagePullBackOff are different points in the same
   failure.
3. COLLECT. Gather evidence with read-only commands only.
4. CONCLUDE. State a root cause with a confidence level and cite the evidence.
5. GATE.   Propose the fix, state its blast radius, and stop.

SAFETY TIERS:
- SAFE_READ: kubectl get/describe/logs/explain/api-resources, helm list/status/
  get/history. Suggest freely.
- SAFE_DIAGNOSTIC: kubectl top, port-forward, auth can-i. Suggest freely.
- HUMAN_APPROVAL_REQUIRED: apply, patch, scale, rollout, edit, cordon, helm
  upgrade/rollback. Propose only. Never present as done.
- DESTRUCTIVE: delete, drain, helm uninstall, anything with --force. Refuse
  unless the operator confirms in a separate, explicit message.

EXIT CODES:
  0   clean exit — check restartPolicy
  1   application error — read --previous logs
  2   shell misuse
  126 permission denied / not executable
  127 command not found — bad ENTRYPOINT or missing binary
  137 SIGKILL — OOMKilled or failed liveness probe
  139 SIGSEGV — segfault
  143 SIGTERM — graceful shutdown, often a normal rollout

HONESTY RULES:
- Distinguish observed output, unverified hypothesis, and unknown state. Never
  blur them.
- Never invent command output. If you need output you do not have, ask for it.
- Say "Low confidence" when the evidence is thin, and name the single command
  that would settle it.
- Never claim a fix worked without verification output.

NEVER suggest `kubectl delete pod` to restart something. It destroys the
--previous logs that usually contain the root cause.

RESPONSE FORMAT:
## Situation
## What I Checked
## Evidence
## Likely Root Cause
## Confidence Level        (High | Medium | Low)
## Recommended Remediation
## Blast Radius
## Human Approval Required
```

---

## 2. Give it the knowledge, not just the rules

A system prompt sets behavior; it does not supply the runbooks. Depending on
what your model supports:

- **Long context** — paste the relevant runbook inline with your question.
- **File upload / RAG** — index `runbooks/`, `symptom-index.yaml` and
  `decision-trees/`. Chunk per runbook: they are ~90 lines and self-contained,
  so one runbook per chunk preserves meaning.
- **Tool calling** — run the [MCP server](mcp.md), or call its functions
  directly (see §4).

---

## 3. Always redact first

```bash
python3 scripts/collect.py -n prod -o evidence-bundle    # bundle, redacted
kubectl describe pod api-1 -n prod | python3 scripts/redact.py   # single command
```

This applies to self-hosted models too. A local model is not automatically
private — its logs, prompt caches, and any telemetry still persist the prompt.
See [evidence-bundles.md](../evidence-bundles.md).

---

## 4. Building on top of it

Everything is importable. No framework, no service.

```python
import sys
sys.path.insert(0, "scripts")

from safety import classify
from redact import redact

verdict = classify("kubectl delete ns prod")
print(verdict.safety)   # DESTRUCTIVE
print(verdict.reason)   # kubectl delete removes resources

clean, stats = redact(raw_kubectl_output)
```

Routing and runbook access, via the MCP server module:

```python
sys.path.insert(0, "integrations/mcp")
from server import route_symptom, get_runbook, list_tools

route = route_symptom("137")
print(route["routes"][0]["runbook"])   # runbooks/pods/oomkilled.md

text = get_runbook("oomkilled")["content"]
```

A minimal agent loop:

```python
def handle(signal, proposed_command):
    route = route_symptom(signal)["routes"][0]
    runbook = get_runbook(Path(route["runbook"]).stem)["content"]

    verdict = classify(proposed_command)
    if verdict.safety not in ("SAFE_READ", "SAFE_DIAGNOSTIC"):
        return f"BLOCKED: {verdict.safety} — {verdict.reason}"

    output, _ = redact(run(proposed_command))
    return llm(system=SYSTEM_PROMPT, context=runbook, evidence=output)
```

The safety check sits **before** execution. That ordering is the whole design —
see `scripts/collect.py` for the same pattern applied to a real command set.

---

## 5. Data structures worth knowing

| File | Shape | Use |
| :--- | :--- | :--- |
| `symptom-index.yaml` | `entries[]` with `signals`, `runbook`, `first_command` | Signal → runbook routing |
| `decision-trees/*.yaml` | `steps[]` with `command`, `outcomes[].condition/next` | Deterministic traversal |
| `commands/*.yaml` | Command → safety tier | Human-facing catalog |
| `schemas/*.json` | JSON Schema | Validate contributions |

Decision trees are the piece worth using if you are building an agent: each step
names one command and branches on a condition evaluated against its output, so
you can drive an investigation without the model choosing the next step.

---

## 6. Limits

- A short system prompt without the runbooks gives you generic Kubernetes advice.
  The runbooks are the value; supply them.
- Small models drop the response format under long context. Re-state it in the
  user turn if that happens.
- Nothing here enforces the tiers at the model layer. If your loop can execute
  commands, gate it in **code** with `classify()`, as in §4.

---

## Related

- [README.md](README.md) — other platforms
- [mcp.md](mcp.md) — tool-calling instead of prompting
- [../safety-model.md](../safety-model.md)
- [../../integrations/generic/system-prompt.md](../../integrations/generic/system-prompt.md)
