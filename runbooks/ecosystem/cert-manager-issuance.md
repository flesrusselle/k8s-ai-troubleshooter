# cert-manager Certificate Stuck Issuing Runbook

## Purpose
Diagnose a cert-manager `Certificate` that never becomes `Ready`, distinct
from `../cluster/certificate-expiry.md`, which covers a certificate that
*was* issued and has since expired. This runbook is for one that was never
issued in the first place.

## When to Use
`kubectl get certificate` shows `READY False` for longer than a few minutes,
or the target Secret it should populate never appears.

## Safety Level
`SAFE_READ`

## Symptoms
- `Certificate` condition `Ready: False`, reason `Issuing`, indefinitely.
- `CertificateRequest` stuck `Pending` with no `Approved` or `Denied` condition.
- `Order`/`Challenge` (ACME issuers) stuck `pending`.
- `too many certificates already issued for: <domain>` in cert-manager's logs.

## Quick Diagnosis

Check the Issuer before any individual Certificate — nothing downstream can
succeed if it isn't `Ready`.

```bash
# 1. Is the Issuer itself healthy? Check this first, always.
kubectl get clusterissuer -o wide
kubectl describe clusterissuer <name>

# 2. The Certificate's own condition and reason
kubectl describe certificate <name> --namespace <namespace>

# 3. Did a CertificateRequest even get approved?
kubectl get certificaterequests --namespace <namespace>
kubectl describe certificaterequest <name> --namespace <namespace>

# 4. ACME-specific: Order and Challenge state
kubectl get order,challenge --namespace <namespace>
kubectl describe challenge <name> --namespace <namespace>

# 5. cert-manager's own controller logs
kubectl logs --namespace cert-manager deployment/cert-manager --tail=100
```

## Detailed Investigation

```text
Certificate not Ready
       ↓
Is the referenced Issuer/ClusterIssuer Ready?
       ↓ no  → fix the issuer first; nothing downstream can succeed
       ↓ yes
Is the CertificateRequest Approved?
       ↓ no  → no approver configured — see below
       ↓ yes
ACME issuer: is the Challenge pending?
       ↓ yes → HTTP01: is the solver path actually reachable through Ingress?
                DNS01: are the DNS-01 solver's provider credentials valid,
                and has the record propagated?
       ↓ no
Does cert-manager's own log mention a rate limit?
       ↓ yes → Let's Encrypt production rate limit hit — switch to staging
                while iterating, wait out the window in production
```

1. **Check the Issuer before the Certificate, every time.** An `Issuer` or
   `ClusterIssuer` with a failed ACME account registration, or an invalid CA
   keypair Secret, blocks every Certificate that references it. Debugging
   individual Certificates first is debugging the symptom.
2. **A stuck `Pending` CertificateRequest with no `Approved`/`Denied`
   condition usually means no approver is configured.** cert-manager's request
   approval mechanism requires something — the built-in auto-approve
   controller for internal issuers, or a policy engine such as
   `approver-policy` — to actively approve requests. Installing a policy
   engine without configuring an approval policy leaves every request
   unapproved forever, with no error, just silence.
3. **HTTP-01 challenges fail for reasons that have nothing to do with
   cert-manager.** The solver needs `/.well-known/acme-challenge/<token>` to
   route through your Ingress to cert-manager's temporary pod. A catch-all
   Ingress rule, a WAF, or DNS not yet pointed at the cluster all produce the
   same stuck-pending Challenge.
4. **DNS-01 challenges fail on credentials or propagation, not cert-manager
   logic.** The solver's cloud DNS provider token needs write access to the
   zone; propagation delay before the ACME server re-checks can also stall a
   Challenge that will succeed on its own given more time. A CAA record
   restricting which CA may issue for the domain silently blocks it too.
5. **Let's Encrypt's production rate limits are easy to self-inflict during
   testing.** Repeated failed attempts against production burn the same
   weekly quota as successful ones. Use the ACME staging directory
   (`https://acme-staging-v02.api.letsencrypt.org/directory`) while iterating
   on a new Issuer or Ingress configuration.
6. **cert-manager has its own validating webhook.** If it is unreachable,
   Certificate and Issuer objects cannot even be created or updated — see
   `../security/admission-webhook.md`; this looks like cert-manager is doing
   nothing when it is actually the webhook blocking the request.

## Decision Tree
Self-contained; branch on issuer health, approval, then challenge type as
above.

## Evidence to Collect
- `ClusterIssuer`/`Issuer` `Ready` condition and message.
- `CertificateRequest` conditions — specifically `Approved`/`Denied`.
- `Order` and `Challenge` state and their solver configuration (HTTP01 vs
  DNS01).
- Whether the ACME directory in use is staging or production.
- cert-manager controller logs for rate-limit or webhook-connectivity errors.
- Whether an approval policy engine is installed and actually configured.

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| ClusterIssuer not Ready | ACME account registration failed, or CA keypair Secret invalid | High |
| CertificateRequest Pending, no Approved/Denied condition | No approver configured for an installed policy engine | High |
| HTTP01 Challenge pending indefinitely | Ingress not routing the ACME solver path, or DNS not pointed at the cluster | High |
| DNS01 Challenge pending indefinitely | Wrong provider credentials, propagation delay, or a blocking CAA record | High |
| `too many certificates already issued` | Let's Encrypt production rate limit hit during testing | High |
| Certificate/Issuer changes never take effect | cert-manager's own webhook unreachable | Medium |
| Secret exists but has wrong/stale content | Ownership conflict with a pre-existing Secret of the same name | Medium |

## Confirmation
Confirm the issuer-first hypothesis before investigating anything else:

```bash
kubectl get clusterissuer <name> \
  -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}{"\t"}{.status.conditions[?(@.type=="Ready")].message}{"\n"}'
```

`False` here explains every Certificate referencing it failing simultaneously,
and no individual Certificate's own state is worth reading until this is
fixed.

## Remediation
Fix the Issuer's account registration or CA keypair, configure or install an
approver for a policy engine that requires one, correct Ingress routing or DNS
records for the challenge type in use, or switch to the ACME staging
directory while iterating. Restore cert-manager's webhook if it is down.

## Blast Radius
Fixing a shared `ClusterIssuer` affects every Certificate across every
namespace that references it — a change intended for one stuck Certificate
can trigger re-issuance attempts cluster-wide. Switching an Issuer's ACME
directory between staging and production changes which CA is trusted by
clients for every certificate it subsequently issues.

## Human Approval Required
- `kubectl apply -f <issuer-or-certificate>.yaml`
- `kubectl delete certificaterequest <name> --namespace <namespace>` — **DESTRUCTIVE**, discards the in-flight request and forces cert-manager to create a new one
- `kubectl delete secret <tls-secret> --namespace <namespace>` to force reissuance — **DESTRUCTIVE**, removes the currently served certificate before a replacement exists

## Verification
```bash
kubectl get certificate <name> --namespace <namespace> \
  -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}{"\n"}'
```
Verified when this reads `True` **and** the target Secret's `tls.crt` matches
the issued certificate — not just that the Certificate object claims
readiness. Confirm client connections actually trust the served certificate,
especially if the Issuer was staging ACME during testing.

## Rollback
Reverting an Issuer configuration change does not un-consume a burned
production rate-limit window — that must be waited out regardless. A deleted
Secret cannot be restored; a fresh issuance must complete before service using
it resumes.

## Related Runbooks
- [../cluster/certificate-expiry.md](../cluster/certificate-expiry.md)
- [../security/admission-webhook.md](../security/admission-webhook.md)
- [../networking/ingress.md](../networking/ingress.md)
- [../helm/helm-ownership.md](../helm/helm-ownership.md)

## Official Documentation
- [cert-manager - Issuer Types](https://cert-manager.io/docs/configuration/)
- [cert-manager - ACME Challenges](https://cert-manager.io/docs/configuration/acme/)
- [cert-manager - CertificateRequest Approval](https://cert-manager.io/docs/concepts/certificaterequest/#approval)
- [Let's Encrypt - Rate Limits](https://letsencrypt.org/docs/rate-limits/)
