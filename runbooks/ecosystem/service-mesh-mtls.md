# Service Mesh mTLS Failure Runbook

## Purpose
Diagnose connections that fail specifically because of mesh mutual-TLS policy
— sidecars are present and healthy, yet traffic between two workloads is
refused or reset.

## When to Use
Both endpoints show a healthy sidecar (`2/2`, not restarting), the target has
Endpoints, DNS resolves, and yet the call still fails — mTLS is the next
thing to check once vanilla connectivity is confirmed innocent.

## Safety Level
`SAFE_READ`

## Symptoms
- `upstream connect error or disconnect/reset before headers` (Istio/Envoy).
- `connection reset by peer` between two meshed services specifically.
- One caller reaches a service fine; another, otherwise identical, cannot.
- Everything mesh-wide broke at once, with no deploy to explain it.

## Quick Diagnosis

Policy is layered — mesh-wide, then namespace, then workload — and the most
specific layer wins. Read all three before concluding which one is at fault.

```bash
# 1. Mesh-wide default
kubectl get peerauthentication default --namespace istio-system -o yaml 2>/dev/null

# 2. Namespace-level override
kubectl get peerauthentication --namespace <namespace> -o yaml

# 3. Workload-specific override — this one wins if it exists
kubectl get peerauthentication --namespace <namespace> \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.selector}{"\t"}{.spec.mtls.mode}{"\n"}{end}'

# 4. Does a DestinationRule override the client side to send plaintext?
kubectl get destinationrule --namespace <namespace> \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.trafficPolicy.tls.mode}{"\n"}{end}'

# 5. The Envoy access log on the receiving sidecar names the flag
kubectl logs <pod> --namespace <namespace> -c istio-proxy --tail=200
```

## Detailed Investigation

```text
mTLS-looking failure
       ↓
Is the caller inside the mesh (has a sidecar)?
       ↓ no  → plaintext from an unmeshed pod hitting a STRICT destination
                is refused by design — this is not a bug
       ↓ yes
Does a workload-level PeerAuthentication exist for the destination?
       ↓ yes → it overrides namespace and mesh defaults; read it, not the others
       ↓ no
Does the namespace-level PeerAuthentication say STRICT?
       ↓ yes → the caller's DestinationRule must set tls.mode to ISTIO_MUTUAL
       ↓ no
Did the mesh's own CA / root certificate just expire?
       ↓ yes → every mTLS connection mesh-wide breaks simultaneously
                — see ../cluster/certificate-expiry.md
```

1. **Policy precedence is workload, then namespace, then mesh — most specific
   wins, unconditionally.** A namespace set to `PERMISSIVE` can still refuse a
   specific workload if that workload has its own `STRICT`
   `PeerAuthentication`, and reading only the namespace-level policy will
   miss this every time.
2. **`PeerAuthentication` (server side) and `DestinationRule` (client side)
   must agree.** `PeerAuthentication: STRICT` says "I only accept mTLS."
   `DestinationRule.trafficPolicy.tls.mode: DISABLE` says "send this
   destination plaintext." Together, a client is instructed to send exactly
   what the server refuses — the single most common real mTLS misconfiguration.
3. **An unmeshed caller hitting a `STRICT` destination failing is correct
   behavior, not a bug to fix by force.** Check for a sidecar on the caller
   before assuming a policy problem.
4. **`PERMISSIVE` mode accepts both mTLS and plaintext**, which is why a
   migration to `STRICT` often "works in testing" and then breaks a caller
   nobody remembered was still unmeshed.
5. **Root CA expiry breaks every mTLS connection in the mesh at the same
   instant**, with no per-service deploy to correlate against — the same
   diagnostic signature as `../cluster/certificate-expiry.md`, scoped to the
   mesh's own identity certificates rather than Kubernetes' own PKI.

## Decision Tree
Self-contained; branch on policy layer and certificate expiry as above.

## Evidence to Collect
- `PeerAuthentication` at mesh, namespace, and workload scope for the target.
- `DestinationRule` `trafficPolicy.tls.mode` on the caller's side.
- Whether the caller pod has a sidecar at all.
- The Envoy access log flag on the failing connection (Istio annotates the
  specific reason, e.g. `UF,URX`).
- Expiry of the mesh's root and intermediate certificates.
- Whether the failure is one caller/callee pair, or mesh-wide and simultaneous.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| Unmeshed caller refused by a meshed destination | STRICT mTLS correctly refusing plaintext — not a bug | High |
| One caller fails, an identical one succeeds | Workload-level PeerAuthentication overriding the namespace default | High |
| `DestinationRule` sets `tls.mode: DISABLE` against a `STRICT` peer | Client/server policy mismatch | High |
| Everything broke mesh-wide, simultaneously, no deploy | Mesh root CA or intermediate certificate expired | High |
| Works after switching namespace policy to `PERMISSIVE` | An unmeshed caller was masked by permissive fallback | Medium |
| Failure only under load, not at low volume | Sidecar resource exhaustion rather than a policy mismatch | Medium |

## Confirmation
Confirm a policy-mismatch hypothesis by testing from a definitely-meshed
source against the same destination:

```bash
kubectl get pod <caller> --namespace <namespace> \
  -o jsonpath='{range .spec.containers[*]}{.name}{"\n"}{end}'
```

If the caller has no sidecar, that is the complete explanation for a `STRICT`
destination refusing it — no further mesh investigation is needed; the fix is
enrolling the caller, not adjusting policy.

## Remediation
Align `PeerAuthentication` and `DestinationRule` so client and server agree,
enroll an unmeshed caller that legitimately needs to reach a `STRICT`
destination, or renew an expired mesh root/intermediate certificate. Do not
"fix" a refused unmeshed connection by loosening `STRICT` to `PERMISSIVE`
mesh-wide — that weakens the guarantee for every other workload to route
around one caller.

## Blast Radius
Changing a namespace- or mesh-level `PeerAuthentication` affects every
workload that policy selects, not only the pair under investigation —
loosening `STRICT` to `PERMISSIVE` removes the mTLS guarantee mesh-wide or
namespace-wide for as long as the change stands. Rotating the mesh root
certificate is a mesh-wide operation that can briefly disrupt every mTLS
connection during rollover if done incorrectly.

## Human Approval Required
- `kubectl apply -f <peerauthentication-or-destinationrule>.yaml`
- Any change to mesh-wide or namespace-wide `PeerAuthentication` — affects every workload the selector matches
- Mesh root/intermediate CA rotation — outside this project's read-only scope; follow your mesh's documented rotation procedure

## Verification
```bash
kubectl logs <pod> --namespace <namespace> -c istio-proxy --tail=50
```
Verified when the specific caller/callee pair that was failing now succeeds,
**and** a deliberately-unmeshed test caller is still refused if the
destination is meant to be `STRICT` — confirming the policy was corrected
rather than weakened.

## Rollback
Revert the `PeerAuthentication`/`DestinationRule` change. If `STRICT` was
loosened to `PERMISSIVE` as an emergency mitigation, treat that as temporary
and tracked — leaving it in place permanently reintroduces the plaintext
fallback the original policy existed to remove.

## Related Runbooks
- [service-mesh-sidecar.md](service-mesh-sidecar.md)
- [../cluster/certificate-expiry.md](../cluster/certificate-expiry.md)
- [../networking/service-unreachable.md](../networking/service-unreachable.md)
- [../networking/network-policy.md](../networking/network-policy.md)

## Official Documentation
- [Istio - Mutual TLS Migration](https://istio.io/latest/docs/tasks/security/authentication/mtls-migration/)
- [Istio - PeerAuthentication](https://istio.io/latest/docs/reference/config/security/peer_authentication/)
- [Istio - DestinationRule TLS Settings](https://istio.io/latest/docs/reference/config/networking/destination-rule/#ClientTLSSettings)
