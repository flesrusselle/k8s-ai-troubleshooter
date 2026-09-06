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
├── helm/                     # Optional read-only CronJob deployment chart
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
| `scripts/k8s_ai.py` | Unified CLI for collection, safety checks, and session history |
| `k8s_ai_core/` | Typed investigation reports and deterministic bundle analysis |
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
command -v helmfile || echo "helmfile missing (optional)"
command -v python3 || echo "python3 missing"
kubectl version --client
helm version --short 2>/dev/null || true
helmfile --version 2>/dev/null || true
kubectl config current-context
```

`kubectl` must already be authenticated to the target cluster. This repository does not create credentials, store kubeconfigs, or connect to a cluster by itself.

**Recommended:** bind the identity running this tool to the least-privilege
`ClusterRole` in [`manifests/rbac/`](manifests/rbac/README.md), rather than
using a personal or cluster-admin kubeconfig. It grants exactly the verbs this
project's own safety classification calls read-only — enforced by the API
server itself, not only by application logic.

### Set up a local checkout

```bash
git clone https://github.com/flesrusselle/k8s-ai-troubleshooter.git
cd k8s-ai-troubleshooter

# Optional but recommended: keep Python dependencies isolated.
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip pyyaml

# Confirm the repository and its contracts are healthy.
python3 scripts/validate.py
python3 -m unittest discover -s tests -q
```

The core scripts use Python's standard library. `PyYAML` is needed for symptom
routing, decision-tree handling, validation, and the MCP adapter. There is no
Kubernetes Python client or hosted service to install. The tool uses the local
`kubectl` and optional `helm` binaries, so keep the checkout on the same
machine as the credentials and cluster context you intend to inspect.

Before collecting anything, verify the context explicitly:

```bash
kubectl config current-context
kubectl auth can-i get pods --all-namespaces
kubectl auth can-i get events --all-namespaces
```

For a stronger boundary, apply the read-only identity described in
[`manifests/rbac/README.md`](manifests/rbac/README.md). Use
`clusterrole-readonly-no-secrets.yaml` when Helm release inspection is not
needed; the standard role can read Secret values because Helm 3 commonly stores
release data in Secrets.

### Helm, Helmfile, and Kubernetes compatibility

| Tool | Support today | Recommended use |
| :--- | :--- | :--- |
| Helm 3 | Supported for read-only release discovery and inspection | Use `helm list`, `status`, `get values`, `get manifest`, and `history`; see [docs/helm-integration.md](docs/helm-integration.md). |
| Helmfile | Not a native collector or MCP tool yet | Use it to identify the intended release/chart/values, then collect and inspect the resulting Kubernetes objects with this repository. Treat `helmfile apply`, `sync`, `destroy`, and `diff --context` as approval-gated or outside automatic execution. |
| Kustomize | Supported for local, read-only manifest rendering and configuration inspection | Use `kustomize build`, `kustomize cfg tree`, or `kubectl kustomize`, then compare the rendered output with live cluster evidence; see [docs/kustomize-integration.md](docs/kustomize-integration.md). |
| Kubernetes | Designed around standard `kubectl` APIs and resource commands | Keep `kubectl` within the Kubernetes version-skew policy for the API server and prefer currently served, non-deprecated APIs. |

The repository does not hard-code a single Kubernetes minor version. This is
intentional: clusters may be several supported releases apart, and the
collector delegates API negotiation to `kubectl`. Before an incident, check
the client and server versions and review the official
[Kubernetes version-skew policy](https://kubernetes.io/releases/version-skew-policy/).
Keep the `kubectl` minor version within the supported skew of the API server,
and upgrade the client before upgrading the cluster when practical.

For upgrade readiness, inspect for deprecated API usage, validate manifests
against the target cluster version, and test the runbooks against a disposable
cluster. This project currently does not discover every deprecated API in Helm
charts or Helmfile states automatically; adding API deprecation scanning is a
high-value future improvement.

The collector continues to use `kubectl` as the cluster source of truth. Other
local tools are only added to the automatic path after their commands have a
specific safety classification and test coverage; an unknown binary is always
blocked by the safety layer.

### Collect evidence first (recommended)

Rather than pasting command output by hand — which is how credentials end up in
a chat log — collect a redacted bundle in one step:

```bash
python3 scripts/collect.py --namespace prod --output evidence-bundle
```

Every command it runs is classified read-only before execution, and all output
is redacted on the way to disk. See [docs/evidence-bundles.md](docs/evidence-bundles.md).

Useful collection variants:

```bash
# Preview the exact commands and safety classifications without contacting the cluster.
python3 scripts/collect.py --dry-run --namespace prod

# Inspect every namespace and write to a named incident directory.
python3 scripts/collect.py --all-namespaces --output incident-2026-09-06

# Skip optional metrics/Helm commands or per-pod logs when access is limited.
python3 scripts/collect.py --namespace prod --no-optional
python3 scripts/collect.py --namespace prod --no-pods
```

The collector is best-effort: missing metrics-server, Helm, permissions, or a
container's previous logs are recorded in the bundle rather than treated as a
diagnosis. Review the generated `README.md` and command failures before sharing
the bundle.

### Investigate an incident and produce a report

The repository now has a unified CLI entry point. It is currently launched with
Python; packaging it as an installed `k8s-ai` executable is a follow-up step.
The CLI is intentionally read-only and is the command boundary that a future UI
should call rather than invoking individual scripts directly.

```bash
# Show all commands.
python3 scripts/k8s_ai.py --help

# Preview a collection plan without contacting the cluster.
python3 scripts/k8s_ai.py collect --namespace prod --dry-run

# Classify a command before considering execution.
python3 scripts/k8s_ai.py safety "kubectl get pods -A" --json

# Review investigation history.
python3 scripts/k8s_ai.py sessions
python3 scripts/k8s_ai.py sessions --tail 5 --json

# Analyze a collected bundle without contacting the cluster.
python3 scripts/k8s_ai.py investigate "Why is checkout-api crashing?" \
      --bundle evidence-bundle --json
```

See [docs/cli.md](docs/cli.md) for the command contract. To produce an
incident report, collect evidence and give the bundle to a human or AI
assistant using one of the integrations below. Ask the investigator to follow
this response structure:

```text
Investigate the evidence bundle at ./evidence-bundle.

Return an incident report with:
1. Executive summary and affected namespace/workloads.
2. Observed facts, quoting the evidence file and object involved.
3. Timeline of relevant warnings, restarts, deployments, and events.
4. Ranked hypotheses with confidence: confirmed, likely, or needs verification.
5. The smallest read-only commands that would confirm each uncertain point.
6. Recommended remediation, including the owning resource and exact file or
      command to change when known.
7. Risk, blast radius, rollback, and verification steps for every recommendation.
8. Unknowns and evidence that was unavailable.

Do not execute or recommend a mutating command without an explicit approval
step. Separate observed facts from hypotheses, and never claim a fix worked
without post-change verification.
```

The bundle investigator produces a conservative deterministic report today. It
does not yet connect to a live cluster, perform adaptive collection, or call an
LLM. Those capabilities will sit behind the same report contract rather than
replacing the evidence-first path.

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

### Review previous investigations

Collection and MCP diagnosis calls append redacted metadata to the local JSONL
session log. The log stores scope, bundle paths, signals, and conclusions; it is
not a replacement for a retention-managed incident system.

```bash
python3 scripts/session_log.py --summary
```

See [docs/session-log.md](docs/session-log.md) for the format and privacy
considerations.

---

## 🧾 Logs, Evidence & Fix Recommendations

### Does It Save Logs?

Interactive runbook sessions do not persist command output automatically. The
explicit collector does write a **redacted evidence bundle** containing pod
logs, descriptions, events, and resource state when you ask it to, and appends
redacted session metadata to the local session log. It never writes the raw
command output to the bundle, but redaction is best effort, so review bundles
before sharing them.

Without the collector, a runbook may instruct an assistant or human to run
commands such as:

```bash
kubectl describe pod <pod-name> --namespace <namespace>
kubectl logs <pod-name> --namespace <namespace> --previous --all-containers
kubectl get events --namespace <namespace> --field-selector involvedObject.name=<pod-name>
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

## 🧭 Current Capabilities and Next Improvements

### Available now

- Read-only cluster evidence collection through approved `kubectl` and Helm commands.
- Redaction before evidence is written to disk.
- Fail-closed command classification and read-only Kubernetes RBAC manifests.
- Signal-to-runbook routing, machine-readable decision trees, and MCP access to the knowledge base.
- Human-readable remediation guidance with an explicit approval boundary.

### High-value improvements

The most useful next steps for pinpointing issues and improving report quality are:

1. **Typed read-only tools:** replace free-form command plans with tools such as `list_unhealthy_pods`, `get_pod_diagnostics`, `get_owner_chain`, `get_recent_events`, and `get_workload_rollout`. Each tool should declare its input/output schema, read-only status, timeout, and required RBAC permissions.
2. **Normalized evidence:** represent facts, timestamps, resource references, derived findings, hypotheses, confidence, and unknowns as structured data so reports are reproducible and easy to compare.
3. **Adaptive investigation:** start with a small scope, then collect only the evidence needed to distinguish competing hypotheses instead of running every command in the cluster.
4. **Cross-resource correlation:** connect Pod -> ReplicaSet -> Deployment/StatefulSet, events -> owning object, Service -> Endpoints/EndpointSlices, Ingress -> Service, PVC -> StorageClass, and workload changes -> incident start time.
5. **Historical and change analysis:** compare current evidence with prior bundles, rollout history, Helm revisions, and available metrics while clearly stating retention limits.
6. **Incident report generation:** emit Markdown and JSON reports with an executive summary, timeline, ranked root causes, evidence citations, confidence, blast radius, recommended fix, rollback, and verification plan.
7. **Native CLI:** add commands such as `k8s-ai investigate pod checkout-api-... --namespace prod`, `k8s-ai report --bundle ...`, and a natural-language entry point that uses the same investigation engine.
8. **Optional observability adapters:** correlate Kubernetes evidence with Prometheus, logs, traces, and deployment systems without making those integrations mandatory.

The design constraint should remain unchanged: Kubernetes and observability
systems are the source of truth; AI helps plan the investigation, correlate
evidence, explain uncertainty, and draft recommendations. It should not invent
cluster state or apply a fix without explicit human approval.

---

## 💰 Zero-Cost Commitment

`k8s-ai-troubleshooter` requires **$0** in external API keys, SaaS platforms, or paid cluster tools. It relies entirely on `kubectl`, standard open-source tools, and local/free AI clients. See [COST.md](docs/COST.md).

## 📦 Container and Kubernetes Deployment

The repository includes an Alpine-based CLI image, Docker Compose support for both
the collector and an Atlassian-designed web UI, and an optional Helm chart providing
scheduled read-only collection and a diagnostics UI dashboard.

See [docs/container-deployment.md](docs/container-deployment.md) for:

- Docker and Compose usage (running collector or UI dashboard);
- Helm chart installation, CronJob, and UI deployment;
- Non-root (UID 65532 / UID 101) and read-only root filesystem defaults;
- Read-only RBAC configuration and projected ServiceAccount tokens;
- Trivy vulnerability scanning and SBOM generation;
- Multi-architecture container builds (`linux/amd64`, `linux/arm64`).

---

## 📜 License

Licensed under the [Apache License, Version 2.0](LICENSE).
