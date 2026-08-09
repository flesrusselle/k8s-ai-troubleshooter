# Getting Started with `k8s-ai-troubleshooter`

`k8s-ai-troubleshooter` provides structured, AI-readable diagnostic knowledge and runbooks for Kubernetes clusters.

---

## ⚡ Prerequisites & Local Environment Setup

Before using `k8s-ai-troubleshooter`, check your local toolchain:

```bash
# Check required tools
command -v kubectl || echo "kubectl missing"
command -v helm || echo "helm missing"
command -v kind || echo "kind missing (optional for local cluster testing)"
command -v python3 || echo "python3 missing"
```

### Installation Options

- **kubectl**: See [Official kubectl installation guide](https://kubernetes.io/docs/tasks/tools/).
- **Helm**: See [Official Helm installation guide](https://helm.sh/docs/intro/install/).
- **kind**: `curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-darwin-amd64 && chmod +x ./kind && mv ./kind /usr/local/bin/kind`

---

## 🛠️ 3 Usage Modes

### Mode 1 — Human SRE Diagnostic Manual
A DevOps engineer or SRE uses `k8s-ai-troubleshooter` runbooks manually. Follow the step-by-step diagnostic paths in `runbooks/` and execute the provided read-only `kubectl` commands.

### Mode 2 — AI-Assisted Troubleshooting (Copy/Paste & Direct Prompts)
A user copies runbook contexts into an AI assistant interface (e.g. ChatGPT, Claude, Copilot) along with anonymized cluster output (`kubectl describe`, logs). The AI analyzes evidence based on the decision trees and identifies probable root causes.

### Mode 3 — Tool-Enabled Autonomous AI Agent
An AI coding assistant or agent (e.g. Antigravity, Claude Code, Cursor, MCP Client) has access to a terminal environment to execute commands.
- The AI loads `integrations/antigravity/SKILL.md` or `.cursorrules`.
- The AI executes `SAFE_READ` commands directly.
- The AI presents evidence and stops for human approval before suggesting any state-changing remediation (`rollout restart`, `patch`, `apply`, `delete`).
