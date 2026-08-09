# Security Policy

## 🛡️ Safety Architecture

`k8s-ai-troubleshooter` is strictly designed around **Read-Only Diagnostics** to prevent unauthorized or unintended modifications to Kubernetes clusters.

### Key Principles

1. **Zero State Mutation**: By default, diagnostic guidelines instruct AI models and scripts to only perform `SAFE_READ` commands (`get`, `describe`, `logs`, `top`).
2. **Human-In-The-Loop**: Any state-changing commands (`kubectl apply`, `kubectl delete`, `kubectl rollout restart`, `helm upgrade`, etc.) require explicit, active approval from a human operator.
3. **Data Privacy & Secret Redaction**: Diagnostic runbooks caution against transmitting sensitive data (Secrets, sensitive ConfigMaps, environment variables containing tokens/passwords) to third-party AI services.

---

## 🔒 Reporting a Vulnerability

If you discover a security vulnerability or unsafe command classification in this repository:

1. **Do NOT open a public GitHub issue.**
2. Send a security report to `security@k8s-ai-troubleshooter.org` (or directly contact repository maintainers).
3. Include detailed steps to reproduce the issue and affected files/runbooks.
4. Maintainers will respond within 48 hours and coordinate a fix.
