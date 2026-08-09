# How `k8s-ai-troubleshooter` Works

The diagnostic loop follows a 12-step deterministic workflow:

```text
 1. Understand Problem
 2. Identify Scope (Namespace vs Cluster-wide)
 3. Verify Context (`kubectl config current-context`)
 4. Discover Affected Workloads (`kubectl get pods -A`)
 5. Gather Evidence (`kubectl describe`, `kubectl logs`)
 6. Correlate Evidence across Pods, Events & Nodes
 7. Traversal via Machine-Readable Decision Tree
 8. Form & Test Hypotheses
 9. Confirm Root Cause with Verified Evidence
10. Report Findings with Confidence Level
11. Suggest Remediation (Detailed Command & Impact)
12. STOP — Require Explicit Human Approval
```

## Evidence vs Hypothesis

The AI agent must explicitly separate facts from assumptions:

* **Observed Fact**: "Container `app` exited with status 137 (OOMKilled)."
* **Verified Evidence**: "Memory usage reached configured limit of 512Mi at 21:44:00."
* **Hypothesis**: "Application leaked memory during bulk processing batch job."
* **Remediation**: "Increase memory limit to 1Gi in `values.yaml` (Human approval required)."
