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
kubectl describe pod <pod-name> --namespace <namespace>

# 2. Inspect configured container image string and imagePullSecrets
kubectl get pod <pod-name> --namespace <namespace> -o jsonpath='{range .spec.containers[*]}{.name}{" Image="}{.image}{"\n"}{end}{"imagePullSecrets="}{.spec.imagePullSecrets}'
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
   kubectl get secrets --namespace <namespace>
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

## Blast Radius
Correcting an image tag replaces every pod in the workload. Creating or
updating an `imagePullSecret` affects every pod in the namespace that references
it. If the registry itself is down, no manifest change helps and the change adds
churn during an incident.

## Human Approval Required
- `kubectl create secret docker-registry ...`
- `kubectl apply -f manifest.yaml`

## Verification
```bash
kubectl get pod <pod-name> --namespace <namespace> \
  -o jsonpath='{.status.containerStatuses[*].state}{"\n"}'
kubectl describe pod <pod-name> --namespace <namespace> | grep -E 'Pulled|Successfully'
```
Verified when a `Successfully pulled image` event appears and the container
reaches `running`. A `Pulled` event referencing a cached image does not prove
registry access was restored — force a node that has never held the image.

## Rollback
Revert the image tag with `kubectl rollout undo`. A deleted or rotated
`imagePullSecret` cannot be un-rotated; it must be recreated with valid
credentials.

## Related Runbooks
- [find-failing-pods.md](find-failing-pods.md)

## Official Documentation
- [Specify ImagePullSecrets on a Pod](https://kubernetes.io/docs/tasks/configure-pod-container/pull-image-private-registry/)
