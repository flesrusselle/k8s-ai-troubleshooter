# Certificate Expiry Runbook

## Purpose
Diagnose failures caused by expired TLS certificates — cluster PKI, webhook
serving certificates, service mesh identities, and Ingress certificates.

## When to Use
Any `x509` error, or a cluster-wide failure that began at a precise moment with
no deploy, no config change, and no traffic spike to explain it.

## Safety Level
`SAFE_READ`

## Symptoms
- `x509: certificate has expired or is not yet valid`.
- `Unable to connect to the server: x509: certificate signed by unknown authority`.
- Every webhook-intercepted operation failing at once.
- Nodes going `NotReady` together, roughly a year after cluster creation.
- Browsers reporting an expired certificate on an Ingress host.

## Quick Diagnosis

The distinguishing signature of certificate expiry is that **nothing changed**.
Correlate the first failure against a wall clock, not against a deploy log.

```bash
# 1. Control plane certificate expiry — run on a control plane node
# kubeadm certs check-expiration

# 2. Client certificate embedded in kubeconfig
kubectl config view --raw -o jsonpath='{.users[0].user.client-certificate-data}' \
  | base64 -d | openssl x509 -noout -enddate 2>/dev/null

# 3. Webhook serving certificates
kubectl get secret -A -o json \
  | python3 -c "
import sys, json, base64, subprocess
for item in json.load(sys.stdin)['items']:
    crt = item.get('data', {}).get('tls.crt')
    if not crt: continue
    out = subprocess.run(['openssl','x509','-noout','-enddate'],
                         input=base64.b64decode(crt), capture_output=True)
    print(item['metadata']['namespace'], item['metadata']['name'], out.stdout.decode().strip())
"

# 4. cert-manager, if in use
kubectl get certificates -A
```

## Detailed Investigation

```text
x509 error / unexplained simultaneous failure
       ↓
Which certificate?
       ↓
kubectl fails for everyone      → API server serving cert, or cluster CA
kubectl fails for one person    → that user's client cert
nodes NotReady together         → kubelet client certs
all admissions fail             → webhook serving cert (see admission-webhook.md)
external HTTPS fails            → Ingress certificate
mesh traffic fails              → mesh identity certificates
```

1. **Kubernetes PKI defaults to one year.** Clusters built with `kubeadm` and not
   upgraded within that window fail on the anniversary. Upgrades renew
   certificates as a side effect, which is why long-running, never-upgraded
   clusters are the ones that break.
2. **Kubelet certificates usually auto-rotate — unless rotation is disabled.**
   When it fails, nodes go `NotReady` in a cluster whose control plane is
   perfectly healthy.
3. **`caBundle` staleness breaks webhooks even when the certificate is valid.**
   Rotating a webhook's serving certificate without updating the `caBundle` in
   its configuration produces `x509: certificate signed by unknown authority` for
   every intercepted request.
4. **The blast radius identifies the certificate.** Everyone affected points at a
   shared certificate; one person affected points at their own credentials; one
   namespace affected points at a webhook or mesh scoped there.
5. **Clock skew imitates expiry.** `certificate is not yet valid` on a
   freshly-issued certificate is a node clock problem, not a PKI problem.

## Decision Tree
Self-contained; branch on blast radius as above.

## Evidence to Collect
- Exact `x509` message — expired, not yet valid, or unknown authority.
- Timestamp of the first failure, to the minute.
- Expiry dates of the candidate certificates.
- Cluster creation or last upgrade date.
- Whether the failure is universal, per-user, or per-namespace.
- Node clock skew, if the error says "not yet valid".

## Root Cause Patterns

| Pattern | Likely Cause | Confidence |
| :--- | :--- | :--- |
| Everything failed at once, no change, ~1 year old cluster | Control plane PKI expired | High |
| Nodes NotReady together, control plane healthy | Kubelet client certificates expired | High |
| Only one operator affected | That user's client certificate or token expired | High |
| All admissions fail with `unknown authority` | Webhook cert rotated, `caBundle` stale | High |
| Ingress HTTPS fails, cluster fine | Ingress certificate or cert-manager renewal failed | High |
| `certificate is not yet valid` | Node clock skew | High |
| cert-manager Certificate not Ready | ACME challenge failing — DNS or HTTP validation | Medium |

## Confirmation
Confirm by reading the expiry date of the specific certificate implicated by the
blast radius:

```bash
echo | openssl s_client -connect <api-server-host>:6443 2>/dev/null \
  | openssl x509 -noout -dates
```

`notAfter` in the past confirms expiry and ends the investigation. If `notAfter`
is in the future, the fault is trust — a stale CA bundle — rather than expiry.

## Remediation
Renew the expired certificate through the mechanism that issued it: `kubeadm
certs renew` for cluster PKI, re-issuance for cert-manager, provider tooling for
managed clusters, or re-authentication for user credentials. Update any
`caBundle` that references a rotated CA. Set an expiry alert afterwards —
recurrence is otherwise certain.

## Blast Radius
Certificate renewal restarts control plane components and briefly interrupts
API availability. Updating a `caBundle` affects every request the webhook
intercepts — cluster-wide, for the duration.

## Human Approval Required
- Certificate renewal on control plane nodes — **DESTRUCTIVE**, requires component restarts and is performed outside this repository's read-only scope
- `kubectl apply -f <updated-webhook-config>.yaml`
- `kubectl delete secret <tls-secret> --namespace <ns>` to force cert-manager reissue — **DESTRUCTIVE**

## Verification
```bash
echo | openssl s_client -connect <api-server-host>:6443 2>/dev/null \
  | openssl x509 -noout -dates
kubectl get nodes
```
Verified when `notAfter` is comfortably in the future and normal operations
succeed for every affected client. Set an expiry alert as part of the fix —
without one, recurrence is certain rather than likely.

## Rollback
Renewal cannot be undone, and the old certificate remains expired. Keep the
previous CA bundle until the new chain is confirmed working, since an incorrect
`caBundle` breaks every intercepted request at once.

## Related Runbooks
- [api-server-unreachable.md](api-server-unreachable.md)
- [../security/admission-webhook.md](../security/admission-webhook.md)
- [../nodes/node-not-ready.md](../nodes/node-not-ready.md)
- [../networking/ingress.md](../networking/ingress.md)

## Official Documentation
- [Certificate Management with kubeadm](https://kubernetes.io/docs/tasks/administer-cluster/kubeadm/kubeadm-certs/)
- [PKI Certificates and Requirements](https://kubernetes.io/docs/setup/best-practices/certificates/)
