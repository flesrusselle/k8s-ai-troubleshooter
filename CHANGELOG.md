# Changelog

All notable changes to `k8s-ai-troubleshooter` are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and versioning follows [Semantic Versioning](https://semver.org/). See
[CONTRIBUTING.md § Releasing](CONTRIBUTING.md#-releasing) for how a release is
cut.

## [Unreleased]

### Added
- Least-privilege RBAC manifests (`manifests/rbac/`) — a `ClusterRole`
  granting exactly the verbs this project's own safety classification calls
  `SAFE_READ`/`SAFE_DIAGNOSTIC`, so "never execute a mutating command" is
  enforced by the API server itself, not only by application logic. A
  `-no-secrets` variant is provided, documenting the real tradeoff that Helm's
  own release storage requires secret read access to function at all.
- `tests/test_rbac_manifest.py`, a conformance test asserting the RBAC
  manifest covers every resource `scripts/collect.py` actually touches.
- `tests/integration/`, a kind-based integration suite inducing four real
  failures (CrashLoopBackOff, a bad image reference, a PVC referencing a
  nonexistent StorageClass, an untolerated taint) against a live API server
  and asserting `route_symptom` resolves the real signal correctly.
  `scripts/integration/run_kind_tests.sh` runs it locally; a new
  `kind-integration-tests` CI job runs it on every PR.
- Four ecosystem runbooks covering GitOps and service mesh, which are not
  vanilla Kubernetes but dominate real production troubleshooting: ArgoCD
  sync failure, service mesh sidecar injection, service mesh mTLS, and
  cert-manager stuck issuing (`runbooks/ecosystem/`).
- `scripts/session_log.py`, an append-only local audit log recording every
  evidence-collection run and every assistant-declared diagnosis, with a
  `--summary` view that flags runbooks recurring three or more times. The
  `log_diagnosis` MCP tool is the assistant-facing side of it.
- `docs/session-log.md`, `docs/reference/README.md` cross-link updates, and
  `manifests/rbac/README.md` documenting the Secrets/Helm RBAC tradeoff.

### Changed
- `scripts/collect.py`'s `find_unhealthy_pods` now reads `kubectl get pods -o
  json` and checks `status.phase`/`containerStatuses[].ready`/waiting-terminated
  reasons directly, instead of parsing the `--no-headers` printed column
  output, which is not a stable API across kubectl versions.
- `integrations/mcp/server.py` version bumped to `1.1.0`, tracking this release.

## [1.0.0] — 2026-08-10

Initial tagged release. Everything from the original engine through four
expansion phases: redaction and evidence collection, per-platform usage
documentation and a real MCP server, 19 additional runbooks, and
Blast-Radius/Verification/Rollback on all 39 runbooks that existed at the time.

### Added
- The initial diagnostic engine: 20 runbooks (Pods, Networking, Storage,
  Nodes, Deployments, Helm), 5 decision trees, classified `kubectl`/`helm`
  command catalogs, JSON Schemas, and integration presets for Antigravity,
  Claude Code, Cursor, ChatGPT, Copilot, and a generic system prompt.
- `scripts/redact.py` — secret redaction by value (private keys, JWTs, cloud
  key formats, URL credentials, `Authorization` headers), by key name, and by
  position (everything under a Secret manifest's `data:`/`stringData:` block).
  Fingerprints values with SHA-256 rather than a constant, so identical
  secrets can be correlated across files without either being disclosed.
- `scripts/collect.py` — a read-only evidence bundler. Every command is
  classified before it runs and refused unless read-only; every captured file
  is redacted before it is written.
- `symptom-index.yaml` — deterministic signal-to-runbook routing, enforced by
  CI so a runbook cannot be added without a route to it and no runbook goes
  unreachable.
- `runbooks/triage.md`, the blast-radius-first entry point.
- `docs/usage/` — a detailed guide per platform (Claude Code, Antigravity,
  Cursor, MCP, ChatGPT, Copilot, generic LLM), each with real setup mechanics,
  a verification question, a worked end-to-end session, and an integration
  troubleshooting table.
- A real MCP server (`integrations/mcp/server.py`) implementing JSON-RPC 2.0
  over stdio — `initialize`, `tools/list`, `tools/call`, `ping` — with
  `list_runbooks`, `get_runbook`, `get_decision_tree`, `query_command_safety`,
  and `route_symptom` tools. It previously implemented no protocol at all
  despite its README advertising four tools.
- 18 additional runbooks: init containers, RBAC `Forbidden`, admission
  webhooks, Pod Security Admission, Jobs/CronJobs, StatefulSets, DaemonSets,
  HPAs, PDBs blocking eviction, ResourceQuota/LimitRange, scheduling
  constraints, service reachability, LoadBalancer pending, multi-attach
  volumes, API server unreachable, certificate expiry, events triage, and
  rollout/rollback.
- `## Blast Radius`, `## Verification`, and `## Rollback` sections on every
  runbook, backfilled with content specific to each rather than boilerplate.
- `docs/reference/` — exit codes, pod states, and event reasons, each routing
  to a runbook.

### Fixed
- Internal documentation links were absolute `file://` paths from one
  machine's filesystem, broken for every other reader; `validate.py` printed
  this as a warning and reported success anyway. Links are now repo-relative
  and the check gates CI.
- Command safety classification searched the raw command string for
  keywords, disagreeing with `commands/*.yaml` on 5 of 17 entries in both
  directions — under-classifying force deletes, over-classifying safe reads.
  Classification is now driven by the parsed argv verb path
  (`scripts/safety.py`) and verified against the catalogs by a conformance
  test.
- The PR release preview described every pull request as "Initial release,
  20 runbooks added" regardless of what the PR changed, because it read
  `git status` (empty in CI) and fell back to listing every file on disk. It
  now diffs against the merge base and reports what actually changed.

[Unreleased]: https://github.com/flesrusselle/k8s-ai-troubleshooter/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/flesrusselle/k8s-ai-troubleshooter/releases/tag/v1.0.0
