# Evidence Bundles & Redaction

Sending real cluster output to an AI assistant is how this repository works. It
is also how credentials leak. This document covers the two tools that make the
first possible without the second.

---

## Why redaction is not optional

The commands this project asks you to run print secrets as a matter of course:

| Command | What it exposes |
| :--- | :--- |
| `kubectl describe pod` | Every environment variable **value**, including passwords injected from Secrets |
| `kubectl logs` | Connection strings, bearer tokens, API keys in stack traces |
| `kubectl get secret -o yaml` | The entire base64 payload |
| `kubectl config view` | `client-key-data`, bearer tokens |
| `kubectl get pods -o yaml` | Inline env values, annotations holding tokens |

Pasting any of that into a hosted assistant publishes it. It may be retained,
logged, or used for training depending on the provider. A password pasted once
must be treated as rotated.

`scripts/redact.py` exists so that the default path is the safe one.

---

## `scripts/redact.py`

Filters secrets out of text while preserving everything useful for diagnosis.

```bash
# Filter a single command
kubectl describe pod api-7d9f --namespace prod | python3 scripts/redact.py

# Redact files in place
python3 scripts/redact.py bundle/*.txt --stats

# Use as a gate: exit 1 if anything sensitive was found
kubectl get secret -o yaml | python3 scripts/redact.py --fail-on-secret > /dev/null
```

### What it does

```text
DB_PASSWORD:   hunter2
        ↓
DB_PASSWORD:   [REDACTED:key-value:f52fbd32]
```

The **key survives**. That matters: "the variable is set but the value is wrong"
and "the variable is missing entirely" are different diagnoses, and blanking the
whole line would erase the difference.

The trailing hash is the first 8 hex characters of the SHA-256 of the value.
Identical secrets produce identical fingerprints, so you can still observe:

```text
pod-spec.txt:  API_TOKEN:  [REDACTED:key-value:9c1185a5]
sidecar.txt:   API_TOKEN:  [REDACTED:key-value:3f79bb7b]
```

…and conclude the sidecar is using a *different* token from the main container —
a complete diagnosis, reached without either value being disclosed.

### What it catches

- **By value**, wherever it appears: private key blocks, JWTs, AWS access key
  IDs, GitHub / Slack / Google / OpenAI / Anthropic key formats, URL credentials
  (`postgres://user:pw@host`), and `Authorization:` headers.
- **By key name**: any key containing `password`, `token`, `secret`, `apikey`,
  `credential`, `dsn`, `passphrase`, and similar.
- **By position**: every value under a `data:` or `stringData:` block, because
  Secret manifests use arbitrary filenames as keys and no name heuristic can
  catch them.

### What it deliberately leaves alone

`LOG_LEVEL`, `REPLICA_COUNT`, image tags, exit codes, `secretName`,
`serviceAccountName` — the things you need to actually debug. Connection strings
keep their host, port and database name once the password is removed, since
"which database is it trying to reach" is usually the question.

### Limits — read these

- It cannot recognise a secret that looks like ordinary text. A password in a
  variable named `MODE` will pass through.
- Fingerprints are not reversible, but they *do* confirm a guess. Someone who
  suspects the password is `hunter2` can hash it and check. Treat a bundle as
  need-to-know, not public.
- It is a filter, not a guarantee. **Review a bundle before sharing it.**

---

## `scripts/collect.py`

Runs the read-only diagnostic set, redacts it, and writes a structured bundle.

```bash
# One namespace
python3 scripts/collect.py --namespace prod

# Whole cluster
python3 scripts/collect.py --all-namespaces --output incident-2026-08-10

# Show what would run, and how each command classifies, without running anything
python3 scripts/collect.py --dry-run --namespace prod
```

### Why bundle at all

Two workflows are painful without it:

- An assistant **with** terminal access spends a turn per `kubectl` call and
  re-derives context each time.
- An assistant **without** terminal access — a browser chat — needs you to paste
  output by hand, which is exactly where unredacted secrets get published.

Collect once, redact once, hand over the directory.

### Two enforced guarantees

1. **It cannot mutate your cluster.** Every command is classified by
   `scripts/safety.py` before execution and refused unless it lands in
   `SAFE_READ` or `SAFE_DIAGNOSTIC`. This is enforced in `run_command`, in front
   of the subprocess — not by convention. `tests/test_collect.py` asserts the
   entire plan classifies read-only, so a bad addition fails CI.

2. **No unredacted copy is ever written.** Output passes through `redact.py` on
   the way to disk, so the secret is not persisted and then cleaned up — it is
   never written at all.

### What lands in the bundle

```text
evidence-bundle/
├── README.md              # Scope, redaction summary, failed commands
├── cluster-info.txt
├── nodes.txt, nodes-detail.txt
├── events.txt             # sorted by lastTimestamp — oldest anomaly first
├── pods.txt, pods-yaml.txt
├── deployments.txt, replicasets.txt, statefulsets.txt, daemonsets.txt
├── services.txt, endpoints.txt, ingress.txt, networkpolicies.txt
├── pvc.txt, storageclasses.txt, persistentvolumes.txt
├── resourcequotas.txt, limitranges.txt, hpa.txt, pdb.txt
└── pods/                  # per unhealthy pod
    ├── prod_api-7d9f_describe.txt
    ├── prod_api-7d9f_logs.txt
    └── prod_api-7d9f_logs-previous.txt
```

Unhealthy pods are detected by status **and** by readiness: a pod showing
`1/2  Running` is collected, because a partially ready pod is a real failure that
the `STATUS` column hides.

`secrets-metadata.txt` lists Secret **names and types only** — the collector
never runs `get secret -o yaml`.

---

## Handing a bundle to an assistant

```text
I have an evidence bundle at ./evidence-bundle from our prod cluster.
Start with runbooks/triage.md, use symptom-index.yaml to route, and follow
the safety tiers in docs/safety-model.md. Do not suggest any command above
SAFE_DIAGNOSTIC without telling me the blast radius first.
```

See [usage guides](usage/README.md) for the exact setup per platform.

---

## Related

- [safety-model.md](safety-model.md) — the four safety tiers
- [../runbooks/triage.md](../runbooks/triage.md) — where an investigation starts
- [../symptom-index.yaml](../symptom-index.yaml) — signal → runbook routing
