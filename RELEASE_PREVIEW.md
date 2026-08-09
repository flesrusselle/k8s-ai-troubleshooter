# 🚀 Release Preview

## Summary
Initial release of `k8s-ai-troubleshooter` — an open-source, model-agnostic, deterministic Kubernetes troubleshooting engine and diagnostic runbook system.

## Added
- **Runbooks**: 20 diagnostic runbooks added covering Pods, Networking, Storage, Nodes, Deployments, and Helm.
- **Decision Trees**: 5 machine-readable YAML decision trees.
- **Command Catalogs**: Classified `kubectl.yaml` and `helm.yaml` command catalogs.
- **AI Integrations**: Antigravity (`SKILL.md`), Claude Code (`CLAUDE.md`), Cursor (`.cursorrules`), ChatGPT, Copilot, Generic AI Prompt, and MCP Server adapter.

## Runbooks
- `runbooks/cluster/cluster-health.md`
- `runbooks/nodes/node-not-ready.md`
- `runbooks/nodes/node-pressure.md`
- `runbooks/networking/network-policy.md`
- `runbooks/networking/coredns.md`
- `runbooks/networking/endpoints.md`
- `runbooks/networking/ingress.md`
- `runbooks/storage/mount-failure.md`
- `runbooks/storage/pvc-pending.md`
- `runbooks/pods/crashloopbackoff.md`
- `runbooks/pods/evicted.md`
- `runbooks/pods/find-failing-pods.md`
- `runbooks/pods/probes.md`
- `runbooks/pods/restarts.md`
- `runbooks/pods/imagepullbackoff.md`
- `runbooks/pods/pending.md`
- `runbooks/pods/oomkilled.md`
- `runbooks/helm/helm-troubleshooting.md`
- `runbooks/helm/helm-ownership.md`
- `runbooks/deployments/deployment-stuck.md`

## Decision Trees
- `decision-trees/node-health.yaml`
- `decision-trees/networking.yaml`
- `decision-trees/helm.yaml`
- `decision-trees/pod-failure.yaml`
- `decision-trees/storage.yaml`

## Commands
- Classified safety levels: `SAFE_READ`, `SAFE_DIAGNOSTIC`, `HUMAN_APPROVAL_REQUIRED`, `DESTRUCTIVE`.

## AI Integrations
- Native Antigravity Skill, Claude Code instructions, Cursor rules, ChatGPT/Copilot instructions, MCP server adapter.

## Helm
- Helm release ownership tracing and values investigation guidelines added.

## Security
- **Strict Read-Only Default**: Zero automated state mutation allowed.
- **Human Approval**: State-changing commands explicitly require human operator consent.

## Testing
- JSON Schema validation
- Runbook section completeness check
- Python offline test suite (`pytest` / `unittest`)
- Command safety classification verification

## Cost Impact
- **$0 Total Cost**: No paid cloud, paid AI APIs, or SaaS tools required.

## Risk
- **Low** (Purely read-only diagnostic knowledge layer).

## Timeline
Created:
August 09, 2026 — 10:17 PM PHT

Last updated:
August 09, 2026 — 10:17 PM PHT
