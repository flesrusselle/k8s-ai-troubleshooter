# Event Reason Reference

The `REASON` column of `kubectl get events` is the most direct statement any
component makes about why something failed. Each reason names the component that
emitted it, which localises the fault immediately.

```bash
kubectl get events --all-namespaces --sort-by=.metadata.creationTimestamp
```

Events expire in roughly an hour. Capture them early — see
[events-triage.md](../../runbooks/cluster/events-triage.md).

---

## Scheduler

| Reason | Meaning | Runbook |
| :--- | :--- | :--- |
| `FailedScheduling` | No node satisfies the pod. The message says whether it is capacity or constraints | [pending.md](../../runbooks/pods/pending.md) / [taints-affinity.md](../../runbooks/scheduling/taints-affinity.md) |
| `Preempted` | Evicted to make room for a higher-priority pod | [evicted.md](../../runbooks/pods/evicted.md) |
| `Scheduled` | Normal — a node was assigned |

Read the `FailedScheduling` message rather than the reason: `Insufficient cpu`
and `had untolerated taint` route to different runbooks and have different fixes.

---

## Kubelet — images

| Reason | Meaning | Runbook |
| :--- | :--- | :--- |
| `Pulling` / `Pulled` | Normal image lifecycle |
| `Failed` | Pull or container start failed — read the message | [imagepullbackoff.md](../../runbooks/pods/imagepullbackoff.md) |
| `BackOff` | Retrying after repeated failure | [crashloopbackoff.md](../../runbooks/pods/crashloopbackoff.md) |
| `ErrImageNeverPull` | `imagePullPolicy: Never` and the image is not present locally | [imagepullbackoff.md](../../runbooks/pods/imagepullbackoff.md) |

---

## Kubelet — lifecycle and health

| Reason | Meaning | Runbook |
| :--- | :--- | :--- |
| `Unhealthy` | A probe failed. The message names which one | [probes.md](../../runbooks/pods/probes.md) |
| `ProbeWarning` | Probe succeeded but returned a warning | [probes.md](../../runbooks/pods/probes.md) |
| `Killing` | Container being stopped — often the consequence of `Unhealthy` | [probes.md](../../runbooks/pods/probes.md) |
| `Created` / `Started` | Normal container lifecycle |
| `Evicted` | Reclaiming node resources | [evicted.md](../../runbooks/pods/evicted.md) |
| `OOMKilling` | Memory limit exceeded | [oomkilled.md](../../runbooks/pods/oomkilled.md) |

`Unhealthy` → `Killing` → `BackOff` is one causal chain, not three faults. Start
at the first.

---

## Storage

| Reason | Meaning | Runbook |
| :--- | :--- | :--- |
| `FailedMount` | Volume could not be mounted. Also covers missing Secrets/ConfigMaps | [mount-failure.md](../../runbooks/storage/mount-failure.md) |
| `FailedAttachVolume` | Volume could not attach — often multi-attach | [multi-attach.md](../../runbooks/storage/multi-attach.md) |
| `ProvisioningFailed` | The provisioner could not create the volume | [pvc-pending.md](../../runbooks/storage/pvc-pending.md) |
| `WaitForFirstConsumer` | **Normal** for `WaitForFirstConsumer` binding — not a fault | [pvc-pending.md](../../runbooks/storage/pvc-pending.md) |
| `FailedBinding` | No PV matches the claim | [pvc-pending.md](../../runbooks/storage/pvc-pending.md) |
| `VolumeResizeFailed` | Expansion failed or is unsupported | [pvc-pending.md](../../runbooks/storage/pvc-pending.md) |

---

## Controllers

| Reason | Meaning | Runbook |
| :--- | :--- | :--- |
| `FailedCreate` | A controller could not create a pod. Very often admission: quota, PSA, or a webhook | [resourcequota.md](../../runbooks/scheduling/resourcequota.md) / [pod-security-admission.md](../../runbooks/security/pod-security-admission.md) |
| `SuccessfulCreate` / `SuccessfulDelete` | Normal |
| `BackoffLimitExceeded` | A Job exhausted its retries | [job-failures.md](../../runbooks/workloads/job-failures.md) |
| `DeadlineExceeded` | `activeDeadlineSeconds` elapsed | [job-failures.md](../../runbooks/workloads/job-failures.md) |
| `FailedGetResourceMetric` | HPA cannot read metrics | [hpa-not-scaling.md](../../runbooks/workloads/hpa-not-scaling.md) |
| `ScalingReplicaSet` | Normal rollout activity |

`FailedCreate` deserves attention: because the *ReplicaSet* is rejected rather
than the Deployment, `kubectl get pods` shows nothing and `describe deployment`
looks healthy. The error is only on the ReplicaSet.

---

## Nodes

| Reason | Meaning | Runbook |
| :--- | :--- | :--- |
| `NodeNotReady` | Node stopped accepting workloads | [node-not-ready.md](../../runbooks/nodes/node-not-ready.md) |
| `NodeHasInsufficientMemory` | Memory pressure | [node-pressure.md](../../runbooks/nodes/node-pressure.md) |
| `NodeHasDiskPressure` | Disk pressure | [node-pressure.md](../../runbooks/nodes/node-pressure.md) |
| `EvictionThresholdMet` | Kubelet is about to start evicting | [node-pressure.md](../../runbooks/nodes/node-pressure.md) |
| `NodeReady` / `Starting` | Normal |
| `Rebooted` | Node restarted — explains simultaneous pod failures | [node-not-ready.md](../../runbooks/nodes/node-not-ready.md) |

---

## Networking

| Reason | Meaning | Runbook |
| :--- | :--- | :--- |
| `SyncLoadBalancerFailed` | Cloud provider refused to provision | [loadbalancer-pending.md](../../runbooks/networking/loadbalancer-pending.md) |
| `EnsuringLoadBalancer` | Provisioning in progress | [loadbalancer-pending.md](../../runbooks/networking/loadbalancer-pending.md) |
| `FailedToUpdateEndpoint` | Endpoint controller could not reconcile | [endpoints.md](../../runbooks/networking/endpoints.md) |

---

## Triage technique

Group before reading. The distribution answers "how big is this?" faster than
any individual event:

```bash
# Which reason dominates?
kubectl get events -A -o json | python3 -c "
import sys, json, collections
c = collections.Counter(i['reason'] for i in json.load(sys.stdin)['items'])
for r, n in c.most_common(15): print(f'{n:5}  {r}')
"

# Which node dominates?
kubectl get events -A --field-selector type=Warning -o json | python3 -c "
import sys, json, collections
c = collections.Counter(i.get('source', {}).get('host', 'unknown')
                        for i in json.load(sys.stdin)['items'])
for h, n in c.most_common(): print(f'{n:5}  {h}')
"
```

One node dominating is a node fault. One reason dominating routes straight to a
runbook. An even spread points at shared infrastructure.

---

## Related

- [exit-codes.md](exit-codes.md)
- [pod-states.md](pod-states.md)
- [../../runbooks/cluster/events-triage.md](../../runbooks/cluster/events-triage.md)
