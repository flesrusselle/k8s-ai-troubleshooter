# Kustomize Integration

Kustomize is useful for diagnosing configuration drift before a change reaches
the cluster. This repository supports standalone Kustomize read-only commands
and the equivalent `kubectl kustomize` rendering path.

## Safe local inspection

```bash
# Render the exact overlay intended for an environment.
kustomize build overlays/prod

# Inspect the resource tree and installed version.
kustomize cfg tree overlays/prod
kustomize version

# Use the kubectl-embedded renderer when standalone Kustomize is unavailable.
kubectl kustomize overlays/prod
```

Rendering is local and does not apply resources to a cluster. The output can be
compared with the evidence bundle to find configuration drift, for example:

- image tags or digests differ from the deployed workload;
- replica counts, resource requests, or probes differ from the overlay;
- namespace, labels, selectors, or service ports do not match;
- a patch or generator is missing from the rendered output;
- an API version is no longer served by the target cluster.

## Investigation workflow

1. Collect live evidence with `scripts/collect.py`.
2. Render the relevant base or overlay locally.
3. Identify the owning Deployment, StatefulSet, DaemonSet, Job, Service, or Ingress.
4. Compare rendered manifests with live objects using a redacted diff.
5. Check events, rollout history, and pod status to distinguish configuration
   drift from runtime or platform failure.
6. Recommend the smallest source change, then include blast radius, rollback,
   and post-change verification. Do not apply it automatically.

## Safety boundaries

The command classifier treats these as diagnostic or read-only:

- `kustomize build <path>`
- `kustomize cfg tree <path>`
- `kustomize cfg cat <path>`
- `kustomize version`
- `kubectl kustomize <path>`

The following are not automatic:

- `kustomize edit` or `kustomize create`, because they modify local files;
- `kustomize fn run`, because it can execute functions;
- `kustomize build --enable-alpha-plugins` and `--enable-exec`, because plugins
  can execute external code;
- `kubectl apply -k` and other cluster operations, which require explicit
  review according to their command classification. `kubectl diff -k` is
  non-mutating but may contact the API server and is treated as a diagnostic
  operation rather than part of the default evidence collector.

Review generated YAML before sharing it. Kustomize resources, generators, and
substitution values may contain credentials, internal endpoints, or customer
data even when the source repository is considered safe.

## Current limitation

Kustomize is currently a local rendering and evidence-correlation capability,
not a full source-control or policy engine. It does not yet automatically
discover every overlay, compare every rendered object to live state, or scan
all deprecated APIs. Those are planned extensions to the normalized evidence
and report-generation layers.