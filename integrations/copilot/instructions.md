# GitHub Copilot Instructions for k8s-ai-troubleshooter

When assisting with Kubernetes diagnostics in GitHub Copilot:

1. Prioritize safe, read-only diagnostic commands (`kubectl get`, `kubectl describe`, `kubectl logs`).
2. Do not automatically suggest state-changing scripts without adding explicit warnings (`HUMAN APPROVAL REQUIRED`).
3. Follow the diagnostic runbooks in `runbooks/` and schemas in `schemas/`.
