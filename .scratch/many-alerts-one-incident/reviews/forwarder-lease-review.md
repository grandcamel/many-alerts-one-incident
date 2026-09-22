# Forwarder service and lease source review

2026-09-22. Independent source review by the delegated Luna reviewer, with root
integration review. This review covers local application source and its stated
interface boundaries, not deployment or native execution.

## Final verdict

PASS for the frozen source and documentation snapshots below. Full-suite results
and the test snapshot are recorded separately in the implementation outcome.

| Artifact | SHA-256 |
| --- | --- |
| `grafana_jsm_sandbox/forwarder_services.py` | `819c3657db8c052065488a16eee6966729f14939dd9a5c1c819394cb3ce3dc91` |
| `grafana_jsm_sandbox/forwarder_leases.py` | `4d7bc53ce9c7410ab2438855568d2da2bfd44dd24c47be909e55c9eea2d4df70` |
| `docs/forwarder-control.md` | `adc3872c4f302429936707abf59c7415043bf33aee4f9ab126a0be3aea12de2f` |
| `.scratch/many-alerts-one-incident/reviews/forwarder-lease-implementation-plan.md` | `bd4a48281501d23358d5f47932686ae5d43eed69ba8c8565bb8c0d1e0914bd53` |

## Corrections incorporated before the final review

- Expiry and heartbeat loss are swept before control refresh, capacity checks and
  snapshots. Stale control cannot register or activate; later renewal cannot revive
  previously revoked leases.
- Launch time cannot precede registration or be in the future. Deadline equality
  denies authority. Invalid, overflowing or regressing clocks hold the registry.
- IDs follow the bounded contract, grants bind the Receiver boot, sentinels use
  constant-time comparison and revoke reasons are closed values.
- Snapshots contain full nonsecret lease metadata. Their byte count includes the
  whole canonical JSON representation, including the count field. Admission
  reserves each record's future state growth plus the full receipt ring and
  top-level metadata. Receipt loss is visible and the loss counter saturates.
- The source and docs explicitly limit `check()` to an instantaneous observation;
  no authenticated control, atomic network dispatch or kernel isolation is claimed.

The reviewer re-read the final lease hash after a comment-only reserve rationale
change and confirmed PASS. Provider calls, native client execution, credential
access, tenant operations and deployment were not performed by this review.

Terra subsequently reviewed the independently authored lease tests after root
strengthened near-capacity state transitions and retention assertions, and
returned PASS at test SHA-256
`47181a5899affca9be99ba04642d21dcb927415ce1fac716832f6c3175f5728a`.
Root's final focused run passed all 50 service/lease tests in 52.68 seconds.
