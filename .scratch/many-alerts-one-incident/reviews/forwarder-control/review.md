# Authenticated control source review

2026-09-22. Independent Sol review plus root integration review. **PASS** at the
five-file snapshot below. Implementation and independent protocol tests were
delegated to Terra; root owns the session integration and lifecycle tests.

| Artifact | SHA-256 |
| --- | --- |
| `grafana_jsm_sandbox/forwarder_control.py` | `b45294a86a1697e41fa8c79ebe2c6e767048778457d3f73ef3109f7eaa4ee3d3` |
| `grafana_jsm_sandbox/forwarder_control_protocol.py` | `51634eb0d05e0f025fb03a6f64bcd44344704bbf385ab2c49510bbf613f196e7` |
| `grafana_jsm_sandbox/forwarder_leases.py` | `14b50bf283f183178efffd562b6900623ab769ca94cf892ead21bf6710262655` |
| `tests/test_forwarder_control.py` | `566eb3eb43ab737d3f6e755e5769a495a5beeea14231634c1f4b94102e92c302` |
| `tests/test_forwarder_control_protocol.py` | `73db613cb605d00477200bcabd13742b083af39d0d4dcc14e5a769d59efc0083` |

## Reviewed guarantees and corrections

UID and challenge proof checks precede displacement. Replacement explicitly
disconnects old authority even for the same boot ID. A private owner identity
fences registry mutations and finalizers under one lock; frame I/O occurs outside
that lock. Rejected sessions relinquish authority before diagnostic writes.
Exceptional closeout latches the registry held, without relying on clock recovery.

Exact schemas and sequence checks prevent generation/boot overrides. Fixed
result projections restrict sentinel output to successful registration. Receiver
authentication checks the Forwarder UID and role-separated proof. The codec
rejects duplicate keys, invalid UTF-8/JSON, oversized/deep/unsupported values,
nonfinite numbers and integers outside signed 64-bit bounds, including integers
too large for Python's general decoder conversion. Read, decode and write share
an absolute frame deadline; fragmentation cannot reset it.

Root's final combined control/protocol run passed **53 tests in 0.63 seconds**.
The reviewer confirmed the source/protocol hashes and separately reviewed and
passed the revised 23 control tests. Earlier intermediate parser/test failures
were corrected before this snapshot. Full-suite evidence is recorded separately
in the outcome; partial reviewer test output is not used as a full-suite result.

The [first full-suite run](full-suite-before-test-coordination-fix.txt) found one
timing-dependent replacement-test failure: waiting for old cleanup consumed the
new connection's artificial 0.5-second idle deadline. Independent diagnosis
confirmed the identity check prevents old cleanup from mutating new authority.
The test now pauses old cleanup before that check, installs and activates the
replacement, then releases old cleanup and verifies both fresh authority and a
new heartbeat. Normal fixture deadlines are two seconds; a separate 0.05-second
controller still tests timeout revocation. Both boot cases pass this deterministic
race test. No production change was made for the timing failure.

Four unauthenticated peers can occupy all connection slots until their bounded
frame deadlines. This is a remaining availability property, not an authority
bypass. Listener access restriction is future provisioning work.

This review does not establish Linux peer credential behavior, private socket or
secret mounts, kernel isolation, credential custody, native/provider/tenant
behavior, deployment acceptance or C2 qualification. No external model harness,
provider call or paid experiment was used for this review.
