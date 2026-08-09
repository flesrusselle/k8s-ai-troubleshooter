# ImagePullBackOff & ErrImagePull Runbook

## Purpose
Diagnose pods failing to pull container images from container registries.

## When to Use
Triggered when pod status displays `ImagePullBackOff` or `ErrImagePull`.

## Safety Level
`SAFE_READ`

## Symptoms
- Pod status: `ImagePullBackOff` or `ErrImagePull`.
- Pod stuck in `Waiting` state.

## Quick Diagnosis

```bash
# 1. Fetch exact event logs explaining image pull failure
kubectl describe pod <pod-name> -n <namespace>

# 2. Inspect configured container image string and imagePullSecrets
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{range .spec.containers[*]}{.name}{" Image="}{.image}{"\n"}{end}{"imagePullSecrets="}{.spec.imagePullSecrets}'
```

## Detailed Investigation

1. **Inspect Event Messages**:
   Look for specific error messages in pod events:
   - `manifest for image:tag not found`: Image tag does not exist in registry.
   - `unauthorized: authentication required`: Missing or invalid `imagePullSecrets`.
   - `net/http: TLS handshake timeout`: Node network or firewall blocking registry access.
2. **Verify Secret Existence**:
   Check if the referenced `imagePullSecret` exists in the target namespace:
   ```bash
   kubectl get secrets -n <namespace>
   ```

## Decision Tree
`decision-trees/pod-failure.yaml`

## Evidence to Collect
- Exact container image repository and tag.
- `imagePullSecrets` array in pod spec.
- Error message string from events.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| `manifest unknown` | Typo in image name or non-existent tag | High |
| `401 Unauthorized` | Missing or expired `imagePullSecret` in namespace | High |
| `connection refused` | Registry network unreachable or corporate proxy issue | Medium |

## Confirmation
Verify whether the image tag exists in the remote registry and credentials match.

## Remediation
Correct image tag in manifest or recreate `imagePullSecret` in namespace.

## Human Approval Required
- `kubectl create secret docker-registry ...`
- `kubectl apply -f manifest.yaml`

## Related Runbooks
- [find-failing-pods.md](file:///Users/flestorres/Desktop/apply/k8s-ai-troubleshooter/runbooks/pods/find-failing-pods.md)

## Official Documentation
- [Specify ImagePullSecrets on a Pod](https://kubernetes.io/docs/tasks/configure-pod-container/pull-image-private-registry/)
