# Security & Provenance

## Security Boundaries & Secrets
* **Check Contexts:** Before security-sensitive changes, verify service accounts, workload identity, privileged containers, and network policies.
* **No Secrets in Output:** NEVER expose passwords, tokens, private keys, or decoded Kubernetes secrets in logs or responses. Prefer metadata inspection.

## Container Images & Provenance
* **Immutable References:** Prefer immutable image references (`repository@sha256:digest`) over tags like `latest`.
* **Tooling:** Use `gcrane` for registry operations (prefer over `crane`).
* **Supply Chain:** Trace artifacts from Source -> Commit -> Build -> Image Digest -> Registry -> Deployment. Do not rely on assumptions.

## Vulnerability Scanning
* Use `syft` for SBOM generation.
* Use `grype` or `trivy` for vulnerability analysis.
* Treat scanner results as evidence. Identify the affected package, severity, and exploitability before proposing upgrades. Do not blindly upgrade dependencies.
