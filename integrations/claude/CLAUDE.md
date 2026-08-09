# Claude Code Guidelines for Kubernetes Troubleshooting (`k8s-ai-troubleshooter`)

You are configured to use the `k8s-ai-troubleshooter` diagnostic engine when answering Kubernetes questions or performing terminal operations.

## Rules for Claude Code

1. **Safety Tiering**:
   - `SAFE_READ` commands (`kubectl get`, `kubectl describe`, `kubectl logs`, `helm list`): Allowed automatically.
   - `HUMAN_APPROVAL_REQUIRED` (`kubectl rollout restart`, `kubectl scale`, `helm upgrade`): Require explicit user prompt approval.
   - `DESTRUCTIVE` (`kubectl delete namespace`, `kubectl delete pvc`, `helm uninstall`): Require double explicit confirmation.
2. **Deterministic Investigation**:
   - Do not jump directly to guessing fixes.
   - Read the appropriate decision tree in `decision-trees/` and follow the diagnostic steps.
   - Collect evidence before concluding root causes.
3. **Response Schema**:
   Follow the response schema defined in `docs/ai-integration.md`.
