# CLI Contract

The unified CLI is the stable boundary for the future web UI. The UI should
invoke these read-only operations or call the same Python functions, rather
than depending on individual shell commands.

## Run locally

```bash
python3 scripts/k8s_ai.py --help
python3 scripts/k8s_ai.py --version
```

The project does not yet install a global `k8s-ai` executable. Until packaging
is added, run it from the repository checkout with `python3 scripts/k8s_ai.py`.
All CLI options use their full names; use `--namespace`, `--output`, and
`--all-namespaces` rather than short aliases.

## Commands

### `collect`

Collects a redacted evidence bundle through the existing fail-closed collector.

```bash
python3 scripts/k8s_ai.py collect --namespace prod --output evidence-bundle
python3 scripts/k8s_ai.py collect --all-namespaces --dry-run
```

It supports the collector's `--no-pods`, `--no-optional`, and `--timeout`
options. Collection failures are recorded in the bundle and do not become a
diagnosis by themselves.

### `safety`

Classifies a command without executing it. JSON is intended for automation and
the future UI:

```bash
python3 scripts/k8s_ai.py safety "kubectl get pods -A" --json
```

The response includes:

- `command`: the submitted command;
- `safety`: `SAFE_READ`, `SAFE_DIAGNOSTIC`, `HUMAN_APPROVAL_REQUIRED`, or `DESTRUCTIVE`;
- `reason`: why the classifier reached the verdict;
- `automatic_execution_allowed`: whether the command is allowed by the current read-only policy.

The CLI never executes the command supplied to `safety`.

### `sessions`

Reads the local JSONL investigation history:

```bash
python3 scripts/k8s_ai.py sessions
python3 scripts/k8s_ai.py sessions --tail 10 --json
python3 scripts/k8s_ai.py sessions --path
```

The log contains redacted metadata, not a substitute for an incident database
or long-term observability system.

### `investigate`

Analyzes an existing redacted evidence bundle with deterministic rules. This
first milestone does not connect to a cluster or call an LLM; it avoids
inventing live state and provides a stable report contract for those layers.

```bash
python3 scripts/k8s_ai.py investigate "Why is checkout-api crashing?" \
	--bundle evidence-bundle

python3 scripts/k8s_ai.py investigate "Why is checkout-api crashing?" \
	--bundle evidence-bundle --json > investigation.json
```

The JSON report contains:

- `status`: `ATTENTION`, `DEGRADED`, `NO_SIGNAL`, or `UNAVAILABLE`;
- `evidence`: observed facts and their bundle sources;
- `hypotheses`: ranked causes with confidence and rationale;
- `recommendations`: non-executed next steps with risk and verification;
- `unknowns`: limits or unavailable evidence.

Supported initial signals include `OOMKilled`, `CrashLoopBackOff`, image pull
failures, scheduling failures, `Pending`, and probe failures. The investigator
never executes a remediation command.

## UI boundary

The next CLI milestone is live `investigate` support over typed read-only
Kubernetes tools, followed by a `report` command. Both should use the existing
normalized evidence contract. The contract should distinguish
observed facts, derived findings, hypotheses, confidence, unknowns,
recommendations, blast radius, rollback, and verification. A UI can then render
the same JSON used by scripts, automation, and AI integrations.

The CLI must remain the safety boundary: unknown tools fail closed, Kubernetes
mutations require explicit approval, evidence is redacted before persistence,
and AI-generated recommendations cannot be presented as verified outcomes.