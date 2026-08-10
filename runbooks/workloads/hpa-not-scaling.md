# HPA Not Scaling Runbook

## Purpose
Diagnose HorizontalPodAutoscalers that do not scale up under load, do not scale
down when idle, or report unknown metrics.

## When to Use
An HPA shows `<unknown>/80%`, stays at `MINPODS` while the workload is saturated,
or oscillates between replica counts.

## Safety Level
`SAFE_READ`

## Symptoms
- `kubectl get hpa` shows `TARGETS  <unknown>/80%`.
- Pods are at 100% CPU and `REPLICAS` does not move.
- Replica count flapping every few minutes.
- HPA reports `FailedGetResourceMetric` or `FailedComputeMetricsReplicas`.

## Quick Diagnosis

```bash
# 1. HPA state — TARGETS is the field that matters
kubectl get hpa -n <namespace>

# 2. The conditions explain the refusal directly
kubectl describe hpa <name> -n <namespace>

# 3. Is the metrics pipeline alive at all?
kubectl top pods -n <namespace>
kubectl get apiservice v1beta1.metrics.k8s.io

# 4. Requests must exist for percentage targets to mean anything
kubectl get deployment <name> -n <namespace> \
  -o jsonpath='{.spec.template.spec.containers[*].resources}{"\n"}'
```

## Detailed Investigation

```text
HPA not scaling
       ↓
TARGETS shows <unknown>?
       ↓ yes → metrics unavailable:
       │        metrics-server missing/unhealthy, or
       │        the container has no resource requests
       ↓ no (metrics readable)
Is the current value actually above target?
       ↓ no  → HPA is behaving correctly; your target is higher than you think
       ↓ yes
At maxReplicas already?
       ↓ yes → raise the ceiling
       ↓ no
New pods Pending?
       → HPA scaled; the scheduler cannot place the pods
```

1. **`<unknown>` is a metrics problem, never a scaling policy problem.** Either
   `metrics-server` is absent or unhealthy, or — much more commonly — the
   container has **no CPU request**. A `cpu: 80%` target is a percentage *of the
   request*; with no request there is no denominator and the HPA cannot compute
   anything.
2. **The HPA scales, the scheduler places.** An HPA that raised `replicas` to 10
   has done its job even if 6 pods are `Pending`. Check pod status before
   concluding the HPA is broken.
3. **Scale-down is deliberately slow.** The default stabilization window is 300
   seconds, so a workload that just spiked will not shrink for at least five
   minutes. This is damping, not a fault.
4. **Averages hide skew.** The HPA uses the mean across pods. One saturated pod
   among nine idle ones will not trigger scaling, which is usually a load
   balancing problem rather than an autoscaling one.
5. **Custom and external metrics need an adapter.** `metrics-server` serves only
   CPU and memory. A target on queue depth or request rate requires a
   Prometheus adapter or equivalent, and `FailedGetExternalMetric` means that
   adapter — not `metrics-server` — is the thing that is broken.

## Decision Tree
Self-contained; branch on whether `TARGETS` reads `<unknown>`.

## Evidence to Collect
- `kubectl get hpa` output, especially `TARGETS`, `MINPODS`, `MAXPODS`, `REPLICAS`.
- HPA conditions: `AbleToScale`, `ScalingActive`, `ScalingLimited`.
- Whether `kubectl top pods` returns data.
- Resource **requests** on every container in the target workload.
- Status of any pods the HPA already created.
- `behavior` block, if the workload flaps.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| `TARGETS <unknown>`, `kubectl top` also fails | metrics-server not installed or unhealthy | High |
| `TARGETS <unknown>`, `kubectl top` works | Container has no CPU/memory request | High |
| `ScalingLimited: True`, reason `TooManyReplicas` | Already at `maxReplicas` | High |
| Replicas raised, pods Pending | Cluster is out of capacity — not an HPA fault | High |
| No scale-down after load drops | Stabilization window, default 300s | High |
| Replica count oscillating | Target too close to steady-state usage | Medium |
| `FailedGetExternalMetric` | Custom metrics adapter missing or misconfigured | High |
| Memory target never scales down | Memory is rarely reclaimed by the process | Medium |

## Confirmation
Confirm the missing-request hypothesis directly:

```bash
kubectl get deployment <name> -n <namespace> \
  -o jsonpath='{range .spec.template.spec.containers[*]}{.name}{"\t"}{.resources.requests}{"\n"}{end}'
```

An empty `requests` alongside a percentage-based HPA target is a complete
explanation for `<unknown>`.

## Remediation
Set CPU and memory requests on the target workload, install or repair
`metrics-server`, raise `maxReplicas`, or tune `behavior` to widen the
stabilization window if the workload is flapping. If pods are Pending after
scale-up, the fix belongs to cluster capacity, not the HPA.

## Human Approval Required
- `kubectl apply -f <deployment-with-requests>.yaml`
- `kubectl patch hpa <name> -n <ns> -p '{"spec":{"maxReplicas":20}}'`
- `kubectl scale deployment/<name> --replicas=<n> -n <ns>` — conflicts with the HPA while it is active

## Related Runbooks
- [../pods/pending.md](../pods/pending.md)
- [../pods/oomkilled.md](../pods/oomkilled.md)
- [../nodes/node-pressure.md](../nodes/node-pressure.md)
- [../scheduling/resourcequota.md](../scheduling/resourcequota.md)

## Official Documentation
- [Horizontal Pod Autoscaling](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- [HPA Walkthrough](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale-walkthrough/)
