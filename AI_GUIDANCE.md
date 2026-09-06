# AI Agent Master Scaffold

This repository contains guidance for AI coding agents working on the Kubernetes troubleshooting
engine. It defines a role, a safety model, and focused playbooks so behavior stays consistent
across tools.

## Entry point

| File | Purpose |
|---|---|
| `AGENTS.md` | Primary agent entry point and initialization sequence. |
| `CLAUDE.md` | Claude Code entry point with the same guidance. |
| `.cursorrules` | Cursor entry point with the same guidance. |

Keep the three entry points aligned when the repository-wide operating model changes.

## Directory structure

```
.
├── AGENTS.md                    entry point / initialization sequence
├── CLAUDE.md      -> AGENTS.md
├── .cursorrules   -> AGENTS.md
├── agents/
│   └── devops_engineer.md       role & operating model
├── rules/
│   ├── mutation_safety.md       risk classification + human review gate
│   ├── memory_management.md     how to use repository documentation as memory
│   ├── final_response.md        required shape of every final answer
│   └── documentation.md         living-documentation conventions
├── skills/
│   ├── infrastructure.md        Kubernetes, Helm, ArgoCD, Terraform, GitHub Actions
│   ├── build_and_containers.md  Maven/Gradle/npm/Nx + Docker heuristics
│   ├── security.md              secrets, image provenance, vulnerability scanning
│   ├── scripting.md             bash vs. python, idempotency, retries
│   ├── troubleshooting.md       bounded debugging loop, diagnostic pivot
│   └── rtk_optimization.md      token-efficient shell command wrapping
└── README.md and docs/            project source of truth and detailed guidance
```

## What each piece does

### `agents/devops_engineer.md` — Role
Casts the agent as a Senior DevOps & Platform Engineer with four priorities, in order:
correctness/safety, reproducibility/minimal changes, low token usage, human review before
mutation. Sets the default workflow — `READ → UNDERSTAND → IDENTIFY SOURCE OF TRUTH → SEARCH →
PLAN → PREVIEW → REVIEW → CHANGE → PROVE → REPORT` — and a read-only-by-default posture using
fast CLI tools (`rg`, `fd`, `jq`, `yq`, `gh`, `gcrane`).

### `rules/` — Guardrails
- **`mutation_safety.md`** — Classifies every action LOW / MEDIUM / HIGH-CRITICAL. HIGH/CRITICAL
  changes (Kubernetes mutations, Terraform applies, CI/CD or registry changes) require a written
  `implementation_plan.md` (mutation, blast radius, rollback, verification) and explicit human
  approval before execution. Bans automatic `git commit`/`push`/`merge`/`rebase`/`reset --hard`,
  and bans exposing secrets or decoded Kubernetes secrets in output.
- **`memory_management.md`** — Treats repository documentation as the source of truth. Only
  stable, reusable facts belong in documentation — never command output or task history.
- **`final_response.md`** — Read-only tasks end in a 2–3 sentence summary. Mutating tasks end in a
  structured **Changes / Why / Validation / Risks & Assumptions / Mutation Status** report.
- **`documentation.md`** — Keeps `README.md` and `docs/` lean: short declarative sentences,
  no pasted code blocks or stack traces, and stale content pruned on every touch.

### `skills/` — On-demand playbooks
Loaded only when a task touches that domain, so irrelevant context never gets carried into a
response:
- **`infrastructure.md`** — Helm/Helmfile before imperative `kubectl`; ArgoCD is the source of
  truth, don't bypass reconciliation; Terraform is `format → validate → plan → review → apply`,
  never auto-applied; GitHub Actions workflows must run on **self-hosted runners only**
  (`ubuntu-latest` etc. banned); manifests get linted (`helm lint`, `kube-linter`, `trivy config`)
  and must set `runAsNonRoot`, drop capabilities, and define resource requests/limits.
- **`build_and_containers.md`** — Detects Maven/Gradle/npm/Nx by their manifest files and uses the
  project's own wrapper; Dockerfiles are checked for multi-stage builds, immutable `@sha256` base
  images, and no secrets baked into layers.
- **`security.md`** — Immutable image references over `latest`, `gcrane` for registry ops, a full
  supply-chain trace (source → commit → build → digest → registry → deploy), SBOMs via `syft`,
  vulnerability scans via `grype`/`trivy` treated as evidence, never blindly auto-patched.
- **`scripting.md`** — Bash for orchestration/pipelines, Python for complex logic; every script
  must be idempotent (safe to re-run); bounded retries only for transient failures.
- **`troubleshooting.md`** — Max 3 debugging attempts, each must add new information; stop at the
  earliest layer that explains a failure; never repeat an already-failed fix; escalates via an
  explicit `[DIAGNOSTIC PIVOT]` back to the human.
- **`rtk_optimization.md`** — Prefixes noisy shell commands (`git`, `kubectl`, test runners) with
  `rtk` to cut token usage.

### Project documentation
`README.md`, `docs/`, runbooks, schemas, and tests are the source of truth for project behavior.
Record stable architectural decisions in the relevant documentation file rather than in chat
history.

## Why it's structured this way
- **One operating model, many tools.** `AGENTS.md`, `CLAUDE.md`, and `.cursorrules` expose the
  same repository guidance to common coding agents.
- **Read-only by default.** Nothing mutates without passing through `mutation_safety.md`'s risk
  tiers; anything HIGH/CRITICAL stops for a human.
- **Skills load on demand.** The agent doesn't pre-load Kubernetes or Terraform context into a
  task about npm — each `skills/*.md` is pulled in only when relevant, keeping responses focused
  and cheap.
- **Documentation is focused, not dumped.** Keep durable facts in the repository documents that
  own them.

## Extending this scaffold
- New domain (e.g. "monitoring")? Add `skills/monitoring.md` and link it from the "Skills &
  Capabilities" list in `AGENTS.md`.
- Learned a durable fact about the project? Write it into the relevant `README.md` or `docs/` file,
  not into a one-off chat answer.
- Changing a safety rule? Edit the single file under `rules/` — every tool that reads `AGENTS.md`
  picks it up immediately.

## Companion presentation
A short slide-deck walkthrough of this scaffold (structure, safety model, Kubernetes/infra
guardrails, do's and don'ts) is available as a published Claude artifact — ask for the link if you
don't have it handy.
