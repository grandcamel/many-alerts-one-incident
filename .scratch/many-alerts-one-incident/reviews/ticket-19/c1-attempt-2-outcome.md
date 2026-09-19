# Ticket 19 — C1 attempt 2 outcome, 2026-09-19

Verdict: **certificate handoff and runtime preparation supported; stopped at the declared interface inventory guard before admission**. The user explicitly requested another attempt and reported closing the MacBook lid. The prior provisioning rejection was preserved as observed evidence rather than attributed to lid closure. This attempt used the [card's attempt-2 amendment](c1-execution-card.md), unchanged image/binary inputs and measurement bounds, and the PEM handoff correction at prototype `79b8ee6fc16be777033f4fc7af6e11a5bf6aa3d1`. No third container attempt followed the stop.

## Correction and preflight

`prototype/local_acceptance/authority.py` now converts the operator's generated public certificate to canonical PEM with `openssl x509 -outform PEM`. The strict service provisioner is unchanged. A regression test exercises the actual Stage A certificate generator, the new conversion, provisioning/config publication and loading the matching certificate/key into a TLS context. Invalid and oversized certificates are rejected. Full suite before the local source commit: **365 passed, 36 skipped**, 401 collected, 20.95 seconds; all 31 C1 preparation tests passed. Ruff and whitespace checks passed. Frozen Stage A/B and production source were not changed.

The initial retry preflight stopped before resource creation because Buildx added padding around the `Driver` field after its first build. Read-back still showed driver `docker` and BuildKit `v0.33.0`. The execution harness was corrected to compare trimmed field values; checks confirmed both spacing variants pass and a different driver fails. That preflight record remains at `/Users/jasonkrueger/maoi-stage-b-evidence/c1/attempt-2-20260919`; the same authorized retry continued in a distinct runtime evidence directory. No identity requirement or runtime limit was relaxed.

## What the runtime attempt established

Both local derivative builds succeeded and returned the same content IDs as attempt 1: Run `sha256:263522d80aefa419778c13eb08c479d27da21a9398e817c935f0b936ec28899f`, services `sha256:f4c61c6e7d435e591d22e50c2a5151e464d45014d9f4d2a668d2fd0676e00c50`. All four containers started. Backend, gateway and Forwarder provisioning succeeded and all three services emitted `ready` receipts.

The retained certificate-format receipt confirms that this run's raw generated certificate did **not** begin with PEM, while the canonical certificate did (1,180 bytes). The converted certificate provisioned successfully. This confirms the helper-to-provisioner format mismatch on the actual retry inputs; it does not recover attempt 1's deleted payload or establish a laptop-sleep cause.

Runtime checks passed before the interface guard:

- Exact container/image/project identities, configured memory/CPU/PID limits, read-only roots, no capabilities, no-new-privileges and absence of published ports matched the card. Run was network-none; Forwarder shared that exact Run namespace.
- Data/control Unix socket read-backs matched UID/GID 2000, mode-700 private directories and mode-600 socket files.
- All **11 baseline package/Skill file hashes** matched; the Linux binary hash matched the pin. Read-only version checks found Claude package 2.1.272 and jira-as 2.0.0 without invoking a model client.
- The Run probe observed UID/GID 1000, effective capabilities zero and `NoNewPrivs=1`. All declared private credential/socket paths and their checked `/proc/<pid>/root` variants were unreadable.
- Writes were denied under `/opt` and `/app` and permitted only in the three exercised allowed directories `/tmp`, `/app/runs` and `/home/demo`. This is the exercised path set, not proof about every possible path.

## Stop and unresolved network claim

The card requires the Run's interface list to contain only `lo`. The actual list was:

`lo`, `tunl0`, `gre0`, `gretap0`, `erspan0`, `ip_vti0`, `ip6_vti0`, `sit0`, `ip6tnl0`, `ip6gre0`.

The IPv4 route table had **zero route rows**; all captured IPv6 route rows named `lo`. The literal interface-list condition nevertheless failed, so the harness stopped before the direct-connect probe, sentinel admission or native MCP launch. This is a real mismatch with the declared guard, **not demonstrated backend reachability**. Interface flags, operational state, addresses and tunnel configuration were not captured, so the evidence cannot classify the extra interfaces as harmless or reachable. Do not waive the guard based on their names or the empty IPv4 table alone.

The next bounded preparation is to capture interface state/address evidence and define a reviewed network-admission predicate that distinguishes mere interface presence from a usable path, while retaining exact-address backend/control denial checks. A new container attempt requires an amended card and explicit authorization; this run was not silently resumed after the runtime stop.

## Cleanup and private evidence

The runtime attempt took **20.561 seconds**, including **8.618 seconds** of cleanup. Authenticated control revocation returned success and produced a `revoke` receipt; no sentinel had been admitted. No 401 post-revocation/native probe ran. Every exact container, network, volume, derived image and experiment image reference was removed and independently verified absent. Both original base images remained at their pinned IDs. Transient signing/server keys, service authority and the private Compose environment file were removed. No broad prune ran; permitted BuildKit cache may remain.

Runtime evidence: `/Users/jasonkrueger/maoi-stage-b-evidence/c1/attempt-2-runtime-20260919`. Its index verifies **62 files / 58,086,301 indexed bytes**, excluding the index itself. Creation: 2026-09-19T23:18:34.907000Z; retention expiry: 2026-10-19T23:18:34.907000Z. Private evidence/root modes and public-trust exceptions follow the card. The scan against all five known secret values reported **zero retained matches**. No MCP bundles exist.

| Artifact | SHA-256 |
| --- | --- |
| `ledger.json` | `eac3c3bf01145ec5deee3fb486270cb92911528b897d7f2c4aedfe9bd353d90e` |
| `certificate-handoff.json` | `daa4db7d4cc5d0b03dfe4ce11d101b6f26b33a9d143038b06465c2bd48f409a2` |
| `baseline-comparison.json` | `e9c4323fc2ee90222d7f5f4d366c1e8dbc566c1fdc5f5d22c1510f9b87f5aa53` |
| `run-snapshot-before.json` | `a755d459735e97ce9adef59d1906f1354f1ec96c837f2fcc96c0de9e328ec60c` |
| `independent-cleanup.json` | `46245c940206e1d07d392da71f3f408fd6e28374de5d9a74c11b35363d66c0dc` |
| `artifact-index.json` | `7a909860341eca03ee9e4fc191ba200e9ab83b8ea281dda33f6aa878a5aa78a3` |

## Acceptance boundary

The certificate/provisioning correction, service readiness, exercised identity/filesystem checks, baseline parity and cleanup have live local-container evidence. The interface guard is refuted as written; usable network isolation remains **inconclusive**. Direct-connect denial, direct TLS/authority probes, all native MCP positive/negative samples, response correlation and native-child containment remain **NOT RUN**. The card's native certificate variants and interruption/restart drills, plus C2/real Grafana, model behavior and intended-cluster acceptance, remain unmeasured.

Ticket 19 remains claimed and ticket 12 blocked. All $12 reservations remain retained; provider actuals remain unknown. No model, paid API, real Grafana, tenant or cloud operation ran. Changes and evidence remain local; nothing was pushed or published.
