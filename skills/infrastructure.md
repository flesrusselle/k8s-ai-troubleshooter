# Infrastructure & Cloud Native (Source of Truth)

## Helm & Helmfile
Investigate Helm (`helm template`, `helm get values`) or Helmfile first for managed workloads.
*Do not immediately patch a Helm workload with imperative `kubectl` commands.*

## GitOps (ArgoCD)
Identify the Application and repository. Change the source of truth; do not bypass reconciliation unless explicitly requested.

## Terraform
Workflow: `Format -> Validate -> Plan -> Review -> Apply`.
*Never automatically apply or destroy.*

## GitHub Actions
When writing or modifying GitHub Actions workflows, **YOU MUST STRICTLY ENFORCE SELF-HOSTED RUNNERS**.
* **Self-Hosted Only:** ALWAYS use `runs-on: [self-hosted]` or specific custom self-hosted labels.
* **NEVER** use GitHub-hosted runners like `runs-on: ubuntu-latest` or `runs-on: macos-latest`.

**Local Testing with `act`:**
Check triggers, contexts, and matrices. Use `act` for local workflow testing to simulate runs before committing.
*Example:* `act pull_request -W .github/workflows/build.yml`
*Explicitly state its limitations (e.g., missing secrets, different environment) to the user when reporting `act` results.*

## Kubernetes & Helm Best Practices
When creating or modifying Kubernetes manifests or Helm charts, **YOU MUST ENSURE BEST PRACTICES AND SECURITY STANDARDS**.
* **Linting & Validation:** ALWAYS run linters before applying or proposing changes. Use `helm lint`, `kube-linter`, `kubeval`, `datree`, or `trivy config` depending on tool availability to validate syntax and catch misconfigurations.
* **Security Contexts:** Enforce strict security contexts where applicable (e.g., `runAsNonRoot: true`, `readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`, drop all capabilities).
* **Resource Management:** Always define reasonable CPU and Memory `requests` and `limits`.
* **Standardization:** Use standardized labels (e.g., `app.kubernetes.io/name`) and avoid hardcoding values in Helm templates (always expose them via `values.yaml`).
