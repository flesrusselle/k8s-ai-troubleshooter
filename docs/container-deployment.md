# Container and Kubernetes Deployment

The repository includes a container image, Docker Compose support for both the
collector and an Atlassian-designed web UI, and an optional Helm chart providing
scheduled read-only collection and an optional diagnostics UI dashboard.

## Docker image

The image is based on Alpine (`python:3.14-alpine`) and runs as UID/GID `65532`.
It includes the CLI, `kubectl` (v1.37.0), and Helm (v4.2.4). Kubernetes and Helm
binaries are downloaded with explicit versions, support multi-architecture builds
(`linux/amd64` and `linux/arm64`), and are verified against their published SHA-256
files during the build.

Build and smoke-test locally:

```bash
docker build \
  --build-arg KUBECTL_VERSION=v1.37.0 \
  --build-arg HELM_VERSION=v4.2.4 \
  --tag k8s-ai-troubleshooter:local \
  .

docker run --rm k8s-ai-troubleshooter:local --help
```

For release builds, pin `PYTHON_IMAGE` to a reviewed immutable digest rather
than a mutable tag:

```bash
docker build \
  --build-arg PYTHON_IMAGE=python:3.14-alpine@sha256:<digest> \
  --tag ghcr.io/example/k8s-ai-troubleshooter:0.2.0 \
  .
```

## Vulnerability and supply-chain checks

Run these checks before publishing an image:

```bash
trivy image --severity HIGH,CRITICAL k8s-ai-troubleshooter:local
syft k8s-ai-troubleshooter:local --output spdx-json=sbom.json
grype sbom:sbom.json --fail-on high
```

Do not add blanket vulnerability ignores. For each finding, update the base
image or dependency, remove the unnecessary package, or document a time-bounded
risk acceptance. Rebuild regularly because Alpine packages and Python base
layers receive security fixes after this repository is released.

## Docker Compose

Docker Compose supports running both the scheduled/one-off collector and the
Atlassian-style single-page diagnostics UI dashboard.

Copy `.env.example` to `.env` or set environment variables:

```bash
cp .env.example .env
```

### 1. Launch the UI Dashboard locally

Preview the dashboard with demo datasets or view existing evidence:

```bash
docker compose up ui
```

Access the UI in your browser at `http://localhost:8080`.

### 2. Run an Evidence Collection

Run the collector against your target cluster using your kubeconfig:

```bash
export KUBECONFIG="$HOME/.kube/config"
export K8S_NAMESPACE=default
docker compose run --rm k8s-ai
```

The collector writes bundles and session records to the shared `evidence` volume.
When the UI is running, it automatically detects and displays live telemetry from
`/evidence/sessions.jsonl`.

The kubeconfig is mounted read-only and is not copied into the image. Use a
least-privilege kubeconfig or ServiceAccount identity; never use a cluster-admin
credential for routine collection.

## Helm Deployment

The Helm chart in `helm/k8s-ai-troubleshooter` provides both the scheduled CronJob
and an optional read-only UI deployment:

```bash
# Lint the chart
helm lint helm/k8s-ai-troubleshooter

# Render templates with CronJob and UI enabled
helm template k8s-ai helm/k8s-ai-troubleshooter \
  --namespace k8s-ai-troubleshooter \
  --set cronJob.enabled=true \
  --set ui.enabled=true

# Deploy to cluster
helm upgrade --install k8s-ai helm/k8s-ai-troubleshooter \
  --namespace k8s-ai-troubleshooter \
  --create-namespace \
  --set cronJob.enabled=true \
  --set ui.enabled=true \
  --set persistence.enabled=true
```

### Security Defaults

- **CronJob**:
  - Read-only ClusterRole verbs (`get`, `list`, `watch`);
  - No Secret read permission by default (`allowSecretRead: false`);
  - Non-root UID/GID `65532`, dropped Linux capabilities, `readOnlyRootFilesystem: true`;
  - Projected short-lived ServiceAccount tokens (`kube-api-access`);
  - Bounded active deadline and TTL after finish.
- **UI Dashboard**:
  - Non-root nginx container (UID 101);
  - Read-only root filesystem with dropped capabilities;
  - Static HTML/CSS served directly via ConfigMaps (no custom image required);
  - Mounts evidence PVC read-only to stream `sessions.jsonl`.

Access the dashboard via port-forward:

```bash
kubectl port-forward -n k8s-ai-troubleshooter svc/k8s-ai-ui 8080:80
```
