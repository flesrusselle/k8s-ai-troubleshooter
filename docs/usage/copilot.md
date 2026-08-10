# Using `k8s-ai-troubleshooter` with GitHub Copilot

Copilot's strength here is not live debugging — it is catching the mistakes that
cause the incidents, at the moment you write them. Use it for the manifest, and
one of the agentic clients for the cluster.

---

## 1. Setup

### Repository-wide instructions

```bash
mkdir -p .github
cp integrations/copilot/instructions.md .github/copilot-instructions.md
```

Copilot Chat picks this up automatically for everyone working in the repository
— which makes it the highest-leverage place to put Kubernetes conventions.

### Path-specific instructions

To apply rules only to manifests, add `.github/instructions/k8s.instructions.md`:

```markdown
---
applyTo: "**/*.yaml"
---

Kubernetes manifests in this repository must:
- set resource requests and limits on every container;
- define readiness and liveness probes with distinct endpoints;
- avoid `:latest` image tags;
- reference Secrets by name, never inline values.

When asked to debug a running workload, follow ../../runbooks/triage.md
and never suggest `kubectl delete pod` as a restart mechanism.
```

---

## 2. Where Copilot actually helps

**Preventing the incident.** Most of the runbooks in this repository exist
because of manifest mistakes that are visible at authoring time:

| Runbook | The manifest mistake behind it |
| :--- | :--- |
| `oomkilled.md` | No memory limit, or one set far below real usage |
| `probes.md` | Liveness probe pointed at a slow dependency, so the app kills itself |
| `imagepullbackoff.md` | `:latest` tag, or missing `imagePullSecrets` |
| `pvc-pending.md` | StorageClass that does not exist in the target cluster |
| `crashloopbackoff.md` | Env var referencing a Secret key that was never created |

Ask Copilot Chat:

```text
Review this Deployment against the failure modes in runbooks/. Which runbook
would I end up reading if I shipped this?
```

**Reviewing a fix.** After an incident, paste the remediation diff and ask what
it breaks.

---

## 3. Where it does not help

Copilot Chat in the editor has no cluster access. It cannot run `kubectl`, see
your pods, or verify anything. For live incidents use
[Claude Code](claude-code.md), [Cursor](cursor.md) or
[Antigravity](antigravity.md); for a browser-only workflow use
[ChatGPT](chatgpt.md) with a redacted bundle.

Copilot in **agent mode** with terminal access behaves like the other agentic
clients — in that case apply the safety tiers from
[safety-model.md](../safety-model.md) and treat this guide's §1 instructions as
the behavioral contract.

---

## 4. Worked example — catching it before it ships

**You:** `Review this against k8s-ai-troubleshooter failure modes.`

```yaml
spec:
  containers:
    - name: api
      image: myrepo/api:latest
      livenessProbe:
        httpGet: { path: /health, port: 8080 }
        initialDelaySeconds: 1
```

**Copilot:**

> Three failure modes here, each with a runbook:
>
> 1. **`image: latest`** → `runbooks/pods/imagepullbackoff.md`. Also makes
>    rollbacks meaningless, since the tag does not identify a build.
> 2. **`initialDelaySeconds: 1`** → `runbooks/pods/probes.md`. If the app takes
>    longer than a second to start, the kubelet kills it, and you get a
>    CrashLoopBackOff whose logs show a *healthy* app being terminated. Use a
>    `startupProbe`, or raise the delay past real startup time.
> 3. **No resource limits** → `runbooks/pods/oomkilled.md`. Without a memory
>    limit the container can starve its node and trigger evictions for unrelated
>    pods.
>
> The second is the expensive one: it produces a confusing symptom, because the
> logs look fine right up to the kill.

---

## 5. Troubleshooting

| Symptom | Cause | Fix |
| :--- | :--- | :--- |
| Instructions ignored | Wrong filename | Must be `.github/copilot-instructions.md` |
| Path rules not applied | Bad glob | Check `applyTo` matches your layout |
| Suggests `kubectl delete pod` | Instructions not loaded | Verify the file is committed and pushed |
| Cannot see runbooks | Not in the workspace | Open the repo, or paste the runbook |

---

## Related

- [README.md](README.md) — other platforms
- [../../integrations/copilot/instructions.md](../../integrations/copilot/instructions.md)
- [../../runbooks/triage.md](../../runbooks/triage.md)
