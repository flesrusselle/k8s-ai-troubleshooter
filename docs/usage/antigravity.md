# Using `k8s-ai-troubleshooter` with Antigravity

Antigravity loads capabilities as **skills** — a folder containing a `SKILL.md`
with YAML frontmatter. This repository ships one at
`integrations/antigravity/SKILL.md`.

---

## 1. Setup

### Option A — activate the repository as your workspace

Open the cloned repository as the active workspace. The skill sits at
`integrations/antigravity/SKILL.md`, and the runbooks it references resolve
relative to the repository root.

### Option B — install into your skills directory

Copy the skill so it is available from any workspace:

```bash
mkdir -p ~/.antigravity/skills/k8s-ai-troubleshooter
cp integrations/antigravity/SKILL.md ~/.antigravity/skills/k8s-ai-troubleshooter/
```

The skill references `runbooks/`, `decision-trees/` and `symptom-index.yaml` by
relative path, so if you install it outside the repository, either copy those
directories alongside it or edit the paths in `SKILL.md` to absolute ones.

> Skill directory locations vary between Antigravity versions. If the path above
> does not match your install, check your version's documentation for where
> skills are discovered — the content of `SKILL.md` is unaffected.

### Verify

```text
Which safety tier is `helm uninstall my-release`, and what runbook covers
a PVC stuck in Pending?
```

Expect **DESTRUCTIVE** and `runbooks/storage/pvc-pending.md`. Anything vaguer
means the skill is not loaded.

---

## 2. What the skill enforces

`SKILL.md` encodes four non-negotiable rules:

1. **Diagnose first, explain second, change nothing without approval.**
2. **Automatic execution is limited to `SAFE_READ`** — `kubectl get`,
   `describe`, `logs`, `top`, `helm list`, `helm status`.
3. **Never auto-execute mutations** — `rollout restart`, `scale`, `patch`,
   `apply`, `delete`, `helm upgrade`, `helm rollback`, `helm uninstall`.
4. **No hallucination** — observed output, unverified hypothesis and unknown
   state must be distinguished from one another.

It also fixes the response structure: Situation → What I Checked → Evidence →
Likely Root Cause → Confidence Level → Recommended Remediation → Human Approval
Required.

---

## 3. Worked example

> **You:** Storage is broken in staging, pods won't start.

**Antigravity:**

> **Verifying context.**
> ```bash
> kubectl config current-context
> ```
> ```text
> staging-eks
> ```
>
> **Scope** — following `runbooks/triage.md`:
> ```bash
> kubectl get pods --namespace staging --field-selector=status.phase!=Running
> ```
> ```text
> NAME              READY   STATUS              RESTARTS   AGE
> analytics-0       0/1     ContainerCreating   0          12m
> analytics-1       0/1     Pending             0          12m
> ```
>
> Two pods of one StatefulSet, two different states. Routing both through
> `symptom-index.yaml`: `ContainerCreating` → `storage/mount-failure.md`,
> `Pending` → `storage/pvc-pending.md`. Loading
> `decision-trees/storage.yaml`.
>
> ```bash
> kubectl describe pod analytics-1 --namespace staging
> ```
> ```text
> Events:
>   Warning  FailedScheduling  pod has unbound immediate PersistentVolumeClaims
> ```
> ```bash
> kubectl get pvc --namespace staging
> ```
> ```text
> NAME               STATUS    VOLUME   CAPACITY   STORAGECLASS   AGE
> data-analytics-1   Pending                       fast-ssd       12m
> ```
> ```bash
> kubectl describe pvc data-analytics-1 --namespace staging
> ```
> ```text
> Warning  ProvisioningFailed  failed to provision volume:
>   rpc error: code = ResourceExhausted desc = volume quota exceeded
> ```
>
> ## Likely Root Cause
> The `fast-ssd` StorageClass cannot provision: the backing account is at its
> volume quota. `analytics-1` is unschedulable because its PVC never bound.
> `analytics-0` is stuck at `ContainerCreating` for the same reason one ordinal
> earlier — StatefulSets create volumes in order.
>
> ## Confidence Level
> **High.** `ProvisioningFailed` names the quota directly, and the ordinal
> pattern matches StatefulSet semantics.
>
> ## Recommended Remediation
> Raise the storage quota with your cloud provider, or reclaim volumes from
> released PVCs. No Kubernetes-side change fixes this.
>
> ## Human Approval Required
> None from me — the fix is outside the cluster. I have run only read-only
> commands. Deleting the PVCs would **not** help and would destroy data.

Note the last line: it named a plausible-looking action and explicitly ruled it
out. That is the "no hallucination" rule doing work.

---

## 4. Adding the MCP server

Antigravity can also consume the [MCP server](mcp.md), which turns runbook
lookup and safety classification into tool calls rather than instructions. Use
both: the skill for behavior, MCP for deterministic knowledge access.

---

## 5. Troubleshooting

| Symptom | Cause | Fix |
| :--- | :--- | :--- |
| Skill never activates | Frontmatter missing or malformed | `SKILL.md` must start with `---`, `name:`, `description:` |
| Runbook paths not found | Skill installed outside the repo | Use absolute paths, or copy `runbooks/` alongside |
| Executes mutations unprompted | Skill not loaded | Re-run the §1 verification question |
| Ignores response structure | Competing instructions | Remove conflicting workspace rules |

---

## Related

- [README.md](README.md) — other platforms
- [../safety-model.md](../safety-model.md)
- [../../integrations/antigravity/SKILL.md](../../integrations/antigravity/SKILL.md)
