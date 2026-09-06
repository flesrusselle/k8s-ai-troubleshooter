# k8s-ai-troubleshooter Helm Chart

Helm chart for deploying **k8s-ai-troubleshooter** — scheduled read-only evidence collection and an Atlassian-designed cluster diagnostics web UI.

## Features

- **Scheduled Collector (CronJob)**: Automatically collects cluster triage bundles (unhealthy pods, events, container logs, describe outputs) on a customizable schedule.
- **Diagnostics Web UI**: Modern Atlassian-styled single-page dashboard for inspecting diagnostic sessions, root cause confidence, and recurring pod failure patterns.
- **Least-Privilege Security**:
  - Read-only ClusterRole verbs (`get`, `list`, `watch`).
  - Secrets read disabled by default (`rbac.allowSecretRead: false`).
  - Runs as unprivileged non-root users (`65532` for collector, `101` for UI).
  - All Linux capabilities dropped (`drop: [ALL]`).
  - Read-only root filesystems on all pods.
  - Projected bounded-lifetime ServiceAccount tokens.

## Prerequisites

- Kubernetes 1.25+
- Helm 3.12+ or Helm 4+

## Quick Start

### 1. Install with Diagnostics UI enabled

```bash
helm upgrade --install k8s-ai ./helm/k8s-ai-troubleshooter \
  --namespace k8s-ai-troubleshooter \
  --create-namespace \
  --set ui.enabled=true
```

Access the dashboard locally via port-forward:

```bash
kubectl port-forward -n k8s-ai-troubleshooter svc/k8s-ai-k8s-ai-troubleshooter-ui 8080:80
# Open http://localhost:8080 in your browser
```

### 2. Enable Scheduled CronJob & Persistent Evidence Storage

```bash
helm upgrade --install k8s-ai ./helm/k8s-ai-troubleshooter \
  --namespace k8s-ai-troubleshooter \
  --create-namespace \
  --set cronJob.enabled=true \
  --set cronJob.schedule="0 * * * *" \
  --set persistence.enabled=true \
  --set persistence.size=5Gi \
  --set ui.enabled=true
```

When both the CronJob and UI share the evidence PVC, the dashboard automatically streams live telemetry from `/evidence/sessions.jsonl`.

## Configuration Values

| Parameter | Description | Default |
|---|---|---|
| `image.repository` | Collector container repository | `ghcr.io/example/k8s-ai-troubleshooter` |
| `image.tag` | Collector image tag | `0.2.0` |
| `image.pullPolicy` | Collector image pull policy | `IfNotPresent` |
| `cronJob.enabled` | Enable scheduled CronJob collector | `false` |
| `cronJob.schedule` | Cron schedule expression | `0 * * * *` |
| `cronJob.concurrencyPolicy` | CronJob concurrency policy | `Forbid` |
| `cronJob.activeDeadlineSeconds` | Maximum execution time in seconds | `300` |
| `cronJob.ttlSecondsAfterFinished` | Auto-cleanup time after job completion | `3600` |
| `persistence.enabled` | Enable PVC for persisting evidence bundles | `false` |
| `persistence.size` | Size of evidence PVC | `5Gi` |
| `persistence.accessMode` | PVC access mode | `ReadWriteOnce` |
| `rbac.create` | Create read-only ClusterRole and Binding | `true` |
| `rbac.allowSecretRead` | Allow reading Secret objects (not recommended unless inspecting Helm releases) | `false` |
| `ui.enabled` | Deploy the nginx-based diagnostics UI | `false` |
| `ui.image` | Container image for UI server | `nginx:1.27-alpine` |
| `ui.replicaCount` | UI pod replica count | `1` |
| `ui.service.type` | UI Service type (`ClusterIP`, `NodePort`, `LoadBalancer`) | `ClusterIP` |
| `ui.service.port` | UI Service HTTP port | `80` |
| `ui.ingress.enabled` | Deploy an Ingress resource for the UI | `false` |
| `ui.ingress.host` | Ingress hostname | `""` |
| `ui.resources.requests.cpu` | UI CPU request | `25m` |
| `ui.resources.requests.memory` | UI Memory request | `32Mi` |

## Validation

Run lint and template verification locally:

```bash
helm lint ./helm/k8s-ai-troubleshooter
helm template test ./helm/k8s-ai-troubleshooter --set cronJob.enabled=true --set ui.enabled=true
```
