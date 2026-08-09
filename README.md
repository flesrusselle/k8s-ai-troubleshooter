# k8s-ai-troubleshooter — AI-Readable Kubernetes Troubleshooting & Runbook Engine

> **Diagnose first. Explain second. Change nothing unless a human explicitly approves the change.**

`k8s-ai-troubleshooter` is an open-source, model-agnostic, deterministic diagnostic engine and troubleshooting knowledge base for Kubernetes. It is designed to be loaded directly by AI coding assistants, MCP clients, autonomous agents, and human SREs.

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
├── docs/                     # Architectural, Safety, Helm & Authoring Guides
├── runbooks/                 # Diagnostic Runbooks (Pods, Net, Storage, Nodes, Helm)
├── decision-trees/           # Machine-Readable YAML Decision Trees
├── commands/                 # Classified Command Catalogs (kubectl, Helm)
├── schemas/                  # JSON Schemas for Runbooks, Decision Trees & Commands
├── integrations/             # Presets for Antigravity, Claude Code, Cursor, ChatGPT, Copilot, MCP
├── examples/                 # Real-World Diagnostic Session Examples
├── scripts/                  # Schema Validation & PR Release Preview Automation
└── tests/                    # Python Validation Test Suite
```

---

## ⚡ Quick Start & Integrations

### 1. Antigravity AI
Copy `integrations/antigravity/SKILL.md` into your Antigravity skills folder or run with `k8s-ai-troubleshooter` as active workspace.

### 2. Claude Code
Point Claude to `integrations/claude/CLAUDE.md`.

### 3. Cursor
Add `integrations/cursor/.cursorrules` to your project root.

### 4. Generic System Prompt
Copy `integrations/generic/system-prompt.md` into your LLM client.

### 5. Local MCP Server
Run `python3 integrations/mcp/server.py` to expose `k8s-ai-troubleshooter` as an MCP service.

---

## 💰 Zero-Cost Commitment

`k8s-ai-troubleshooter` requires **$0** in external API keys, SaaS platforms, or paid cluster tools. It relies entirely on `kubectl`, standard open-source tools, and local/free AI clients. See [COST.md](file:///Users/flestorres/Desktop/apply/k8s-ai-troubleshooter/docs/COST.md).

---

## 📜 License

Licensed under the [Apache License, Version 2.0](file:///Users/flestorres/Desktop/apply/k8s-ai-troubleshooter/LICENSE).
