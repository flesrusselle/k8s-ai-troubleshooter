# k8s-ai-troubleshooter — AI-Readable Kubernetes Troubleshooting & Runbook Engine

> **Diagnose first. Explain second. Change nothing unless a human explicitly approves the change.**

`k8s-ai-troubleshooter` is an open-source, model-agnostic, deterministic diagnostic engine and troubleshooting knowledge base for Kubernetes. It is designed to be loaded directly by AI coding assistants, MCP clients, autonomous agents, and human SREs.

Pin to a [tagged release](https://github.com/flesrusselle/k8s-ai-troubleshooter/tags) rather than `main` if you depend on this not changing under you — see [`CHANGELOG.md`](CHANGELOG.md).

---

## 💡 What is this?

Rather than generating generic advice from probabilistic LLM training data, `k8s-ai-troubleshooter` provides structured, Kubernetes-native diagnostic paths, command catalogs, machine-readable decision trees, and strict safety guards.

```text
AI Assistant / Agent
      │
      ▼
k8s-ai-troubleshooter (Knowledge Base & Runbook Engine)
      │
      ├── Diagnostic Rules & Machine-Readable Decision Trees
      ├── Safety Classifications (SAFE_READ vs HUMAN_APPROVAL_REQUIRED)
      ├── Standardized kubectl & JSONPath Queries
      └── Helm Release Ownership & Value Inspection
      │
      ▼
Kubernetes Cluster (Read-Only Inspection)
      │
      ▼
Observed Evidence -> Root Cause Hypothesis -> Evidence Verification -> Human Approval
```

---

## 🎯 Who is it for?

* **AI Coding Assistants & Agents**: Antigravity, Claude Code, Cursor, ChatGPT, GitHub Copilot, MCP Clients, local LLMs.
* **SREs & DevOps Engineers**: Seeking structured, repeatable, evidence-driven Kubernetes diagnostic runbooks.
* **Platform Teams**: Enforcing zero-trust read-only diagnostic boundaries for AI tools.

---

## 🛡️ Safety Model & Non-Negotiable Rules

All operations are strictly categorized into safety tiers:

| Safety Classification | Description | Automatic Execution Allowed? | Examples |
| :--- | :--- | :--- | :--- |
| `SAFE_READ` | Non-mutating read-only cluster state queries | **YES** | `kubectl get pods -A`, `kubectl describe pod`, `kubectl logs` |
| `SAFE_DIAGNOSTIC` | Non-destructive diagnostic commands | **YES (If read-only)** | `kubectl top pods`, `kubectl explain` |
| `HUMAN_APPROVAL_REQUIRED` | Mutating actions (restarts, updates, scaling) | **NO — REQUIRES HUMAN APPROVAL** | `kubectl rollout restart`, `kubectl scale`, `helm upgrade` |
| `DESTRUCTIVE` | Destructive operations (deletion, purge) | **NO — NEVER AUTOMATED** | `kubectl delete namespace`, `kubectl delete pvc` |

### Absolute Safety Rule

> **NEVER automatically execute a command that deletes, restarts, scales, patches, applies, modifies, upgrades, rolls back, or uninstalls resources or cluster networking/storage.**

---

## 🚀 How It Works: Example Diagnostic Session

When a user asks:
> *"Check why my pod is failing in the cluster."*

The AI assistant follows this deterministic path:

1. **Check Context**: Identifies active cluster context via `kubectl config current-context`.
2. **Scan Workloads**: Lists failing workloads across namespaces using `kubectl get pods -A`.
3. **Inspect Pod State**: Gathers detailed state and events via `kubectl describe pod`.
4. **Collect Logs**: Fetches current and previous logs via `kubectl logs` and `kubectl logs --previous`.
5. **Trace Workload Ownership**: Traverses `Pod -> ReplicaSet -> Deployment` owner references.
6. **Check Helm Ownership**: Checks if the resource is managed by Helm via `helm list -A`.
7. **Evaluate Decision Tree**: Follows `decision-trees/pod-failure.yaml` to narrow hypotheses.
8. **Determine Root Cause**: Reports observed evidence, confidence level, and verified cause.
9. **Recommend Remediation**: Presents the exact remediation command and **stops for human approval**.

---

## 📂 Repository Structure

```text
k8s-ai-troubleshooter/
├── symptom-index.yaml        # Signal → Runbook Router (the entry point)
├── docs/                     # Architecture, Safety, Usage Guides & Reference Tables
├── runbooks/                 # Diagnostic Runbooks (start at runbooks/triage.md)
├── decision-trees/           # Machine-Readable YAML Decision Trees
├── commands/                 # Classified Command Catalogs (kubectl, Helm)
├── schemas/                  # JSON Schemas for Runbooks, Trees, Commands & Index
├── manifests/rbac/           # Least-privilege ClusterRole for running this tool
├── integrations/             # Presets for Antigravity, Claude Code, Cursor, ChatGPT, Copilot, MCP
├── examples/                 # Real-World Diagnostic Session Examples
├── scripts/                  # Redaction, Evidence Collection, Safety & Validation
├── scripts/integration/      # Runner for the kind-based integration suite
└── tests/                    # Python Test Suite (tests/integration/ needs a real cluster)
```

### Key scripts

| Script | Purpose |
| :--- | :--- |
| `scripts/collect.py` | Collect a redacted, read-only evidence bundle for an assistant to analyse |
| `scripts/redact.py` | Strip secrets from cluster output while preserving diagnostic detail |
| `scripts/safety.py` | Classify any `kubectl` / `helm` command into a safety tier |
| `scripts/session_log.py` | Review the audit log of past diagnoses — see [docs/session-log.md](docs/session-log.md) |
| `scripts/validate.py` | Structural validation of runbooks, schemas, routing and links |

### Reference tables

Lookup tables mapping raw Kubernetes signals to their meaning and runbook:
[exit codes](docs/reference/exit-codes.md), [pod states](docs/reference/pod-states.md),
[event reasons](docs/reference/event-reasons.md).

---

## ⚡ Quick Start & Integrations

### Prerequisites

Install and configure the tools you want the assistant to use:

```bash
command -v kubectl || echo "kubectl missing"
command -v helm || echo "helm missing"
command -v python3 || echo "python3 missing"
kubectl config current-context
```

`kubectl` must already be authenticated to the target cluster. This repository does not create credentials, store kubeconfigs, or connect to a cluster by itself.

**Recommended:** bind the identity running this tool to the least-privilege
`ClusterRole` in [`manifests/rbac/`](manifests/rbac/README.md), rather than
using a personal or cluster-admin kubeconfig. It grants exactly the verbs this
project's own safety classification calls read-only — enforced by the API
server itself, not only by application logic.

### Collect evidence first (recommended)

Rather than pasting command output by hand — which is how credentials end up in
a chat log — collect a redacted bundle in one step:

```bash
python3 scripts/collect.py -n prod -o evidence-bundle
```

Every command it runs is classified read-only before execution, and all output
is redacted on the way to disk. See [docs/evidence-bundles.md](docs/evidence-bundles.md).

### Option 1: Use It as a Human Runbook Library

1. Start at [`runbooks/triage.md`](runbooks/triage.md) to establish blast radius, then
   match the observed signal against [`symptom-index.yaml`](symptom-index.yaml).
2. Run the listed `SAFE_READ` commands yourself, such as `kubectl get pods -A`, `kubectl describe pod`, and `kubectl logs`.
3. Compare the observed output with the matching decision tree under `decision-trees/`.
4. Apply any remediation only after reviewing the impact.

Good starting points:

- `runbooks/pods/find-failing-pods.md`
- `runbooks/pods/crashloopbackoff.md`
- `runbooks/pods/oomkilled.md`
- `runbooks/networking/ingress.md`
- `runbooks/storage/pvc-pending.md`

### Option 2: Use It With an AI Assistant

Each platform has a detailed guide with setup, permissions, a worked end-to-end
session, and integration troubleshooting — start at
[docs/usage/](docs/usage/README.md):

| Platform | Guide | Preset |
| :--- | :--- | :--- |
| Claude Code | [docs/usage/claude-code.md](docs/usage/claude-code.md) | `integrations/claude/CLAUDE.md` |
| Antigravity | [docs/usage/antigravity.md](docs/usage/antigravity.md) | `integrations/antigravity/SKILL.md` |
| Cursor | [docs/usage/cursor.md](docs/usage/cursor.md) | `integrations/cursor/.cursorrules` |
| MCP clients | [docs/usage/mcp.md](docs/usage/mcp.md) | `integrations/mcp/server.py` |
| ChatGPT | [docs/usage/chatgpt.md](docs/usage/chatgpt.md) | `integrations/chatgpt/instructions.md` |
| GitHub Copilot | [docs/usage/copilot.md](docs/usage/copilot.md) | `integrations/copilot/instructions.md` |
| Any other LLM | [docs/usage/generic-llm.md](docs/usage/generic-llm.md) | `integrations/generic/system-prompt.md` |

Then ask a concrete diagnostic question, for example:

```text
Find all failing pods in the current cluster and explain the likely root cause.
```

The assistant should execute only read-only diagnostic commands automatically, gather evidence, map the evidence to a decision tree, and stop before any mutating fix.

### Option 3: Run the Local MCP Adapter

The MCP adapter exposes the repository's runbooks, decision trees, and command safety classifier to MCP-compatible clients.

```bash
python3 integrations/mcp/server.py
```

For a smoke test:

```bash
python3 integrations/mcp/server.py --test
```

See `integrations/mcp/README.md` for the exposed MCP tools.

---

## 🧾 Logs, Evidence & Fix Recommendations

### Does It Save Logs?

No. `k8s-ai-troubleshooter` does **not** persist Kubernetes logs, pod descriptions, events, or command output by default.

When a pod problem is detected, the runbooks may instruct an assistant or human to run commands such as:

```bash
kubectl describe pod <pod-name> -n <namespace>
kubectl logs <pod-name> -n <namespace> --previous --all-containers
kubectl get events -n <namespace> --field-selector involvedObject.name=<pod-name>
```

Those commands print evidence to the current terminal or AI session. If you want a permanent audit trail, save the output yourself or configure the integrating agent to write a session report outside this repository. Be careful with saved logs because they may contain secrets, tokens, customer data, hostnames, or internal service names.

### Does It Detect Pod Problems Automatically?

The repository provides deterministic diagnostic instructions and decision trees. It does not run as a background controller, Kubernetes operator, or always-on monitoring daemon.

Detection happens when a human or AI assistant runs the diagnostic workflow. For pod issues, the common starting command is:

```bash
kubectl get pods -A --field-selector=status.phase!=Running,status.phase!=Succeeded
```

The workflow then inspects container status, restart counts, prior logs, events, owner references, scheduling state, node pressure, Helm ownership, and related Kubernetes objects depending on the symptom.

### Does It Compile All Possible Fixes?

It compiles likely fixes from the matching runbooks and decision trees, prioritized by observed evidence. The intended output is:

- observed facts from the cluster;
- likely root cause;
- confidence level;
- commands used to verify the diagnosis;
- recommended remediation;
- impact or risk of the remediation;
- exact command or file change when one is appropriate;
- a hard stop for human approval before any mutating action.

It does not blindly list every generic Kubernetes fix. The goal is to reduce noise by recommending fixes that match the actual evidence, such as increasing memory limits for confirmed `OOMKilled`, fixing image tags or `imagePullSecrets` for `ImagePullBackOff`, adjusting resource requests for `Pending`, or reviewing application errors for `CrashLoopBackOff`.

---

## 💰 Zero-Cost Commitment

`k8s-ai-troubleshooter` requires **$0** in external API keys, SaaS platforms, or paid cluster tools. It relies entirely on `kubectl`, standard open-source tools, and local/free AI clients. See [COST.md](docs/COST.md).

---

## 📜 License

Licensed under the [Apache License, Version 2.0](LICENSE).
