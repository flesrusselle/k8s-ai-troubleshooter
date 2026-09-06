# Mutation & Safety Protocol

Any operation that can mutate state (`kubectl apply`, `git push`, `terraform apply`) requires extreme care.

## Risk Classification
* **LOW:** Read-only, local searches, dry-runs.
* **MEDIUM:** Local file edits, local builds.
* **HIGH / CRITICAL:** CI/CD changes, K8s mutations, Terraform applies, registry changes.

## The Human Review Gate
For HIGH/CRITICAL changes, you MUST STOP and wait for human approval before execution.

## Planning Phase
For HIGH/CRITICAL tasks, create an `implementation_plan.md` artifact detailing:
1. The mutation
2. Resources affected (Blast Radius)
3. Rollback steps
4. Verification plan
*Do not execute until the user approves this plan.*

## Git Safety
NEVER automatically `git commit`, `push`, `merge`, `rebase`, or `reset --hard`. Do not overwrite unrelated work.

## Security
Never expose secrets, tokens, or decoded K8s secrets in command output.
