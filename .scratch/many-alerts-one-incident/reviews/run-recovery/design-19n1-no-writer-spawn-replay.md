# 19n1: no-writer spawn and release claim replay

Status: proposed local source design, 2026-09-25. Fixed point: `fd4e046`.
Authority: reviewed 19n spawn/release contract, ADR 0012, ticket 37 and the
existing `(launch_claim, 3)` projection. This design registers no writer,
spawns no process, verifies no witness and permits no dispatch.

## Scope and interpretation

Add strict private v3 journal schemas and pure replay for a single
`spawn_attestation`, `release_intent` and `release_observation` bound to the
one existing launch claim. These records are **claims**, even when their
syntax and journal chain verify. The inspected state must remain
`outstanding_unqualified_launch_claim` with a separate claimed phase and
digest. Neither a release observation nor a missing one establishes effect,
child absence, Forwarder closeout, reservation or report authority. No
production writer, gate, launcher, permit book or listener may import a
positive result from this unit.

## Proposed record shapes

Each record has actor `receiver`, one-record commit, exact IDs and data keys,
canonical bytes, a type-specific maximum and a tagged self-digest over
`event_id`, IDs and all other data. All IDs follow the existing UUID or
bounded opaque grammar, all digests are lowercase hex64, and timestamps are
exact same-boot monotonic microseconds. Every record points to the
immediately current journal head and the exact predecessor claim event ID,
digest and commit sequence. Replay replans the record and requires
byte-for-byte equality, including the computed digest and size. A changed
boot, stale head, duplicate phase or reused claim identity fails closed.
The pre-release records reject a new hold and require an observation before
the work deadline. A post-release observation may be appended after a new
hold or the hard deadline: it preserves historical acknowledgment evidence
but never restores authority, clears the hold or extends the deadline.

* `spawn_attestation` (ordinary, at most 4,096 bytes) carries the launch
  claim ID/digest, Run and attempt IDs, current head, observation time,
  blocked acknowledgment digest, opaque anchor-key digest, bounded witness
  kind and verifier version, opaque locator, witness identity digest and
  protected-registry entry digest. It states only that the writer claimed a
  blocked identity at that moment. The source cannot validate registry
  custody or a stable process identity.
* `release_intent` (ordinary, at most 4,096 bytes) carries the exact
  attestation identity/digest, current head, intended release time and a
  sorted activation list matching every claimed Forwarder grant and
  service. Each activation has bounded grant ID, activation read-back
  digest and same-boot monotonic time from the attestation observation
  through the release-intent time, strictly before grant expiry and the
  Run work deadline.
  It is one-use; the record cannot itself release the child. The future
  writer must independently requalify the **new** head and ledger after this
  commit, then perform all reviewed 19n step-5 checks before sending a byte:
  current approved reference scope and immediate revocation, venue, grants
  and continuous Forwarder owner session, deadlines, and exact barrier/child
  identity.
* `release_observation` (recovery, at most 2,048 bytes) carries the exact
  release intent identity/digest, current head, same-boot observed time no
  earlier than the intent, and a bounded acknowledgment digest tied to that
  intent. It says only that the writer claimed a trusted barrier
  acknowledgment. It is never inferred from a release intent, process exit
  or missing pipe. Its append accepts intervening holds and elapsed Run
  deadlines because those do not erase an already observed release.

No action-intent/result or terminal/absence record is registered in 19n1.
Their future schemas must preserve the 19n crash distinctions; this unit
cannot clear a dispatch hold or retire the outstanding Run. The release
intent uses ordinary capacity because it advances toward exposure, while
the observation uses recovery capacity so an already-sent release can still
be recorded after the ordinary region fills. An application writer may not
start a child until it has reserved worst-case space for all future action,
terminal and reconciliation evidence; this unit does not define that full
reserve and therefore enables no child creation. Before a future writer
creates a child it must atomically protect at least 8,960 ordinary bytes
for the attestation and release intent, plus 2,432 recovery bytes for a
possible release observation, **in addition** to the separately designed
action, terminal and reconciliation reserve. Concurrent admission cannot
spend these protected bytes. This local source slice creates no such escrow.

## Capacity and replay limits

The current journal has a 112 MiB ordinary region, 128 MiB total region,
16,384-byte absolute record ceiling and 384-byte charged record overhead.
The new types consume the existing `logical_bytes` budget exactly once.
There is at most one instance of each type in the current one-Run
projection. The two ordinary records must individually fit below the
ordinary ceiling; the recovery observation must fit below the total ceiling.
At most 10,240 bytes of new canonical record bodies plus 1,152 bytes of
overhead can be charged by a complete three-record 19n1 sequence. The
future writer must preflight its own larger, finite action/terminal reserve
before spawn; satisfying this local bound is insufficient.

The source test matrix covers maximal valid shapes and size edges, all
three crash prefixes, forged recomputed records, duplicate/reordered
records, stale basis, boot/generation change, holds and expiry, activation
omission/duplication, capacity edges, mixed-version real-store reopen and
older-decoder `journal_schema_unsupported` refusal. Stopped inspection
must use only an independently verified exact journal head. The original
v1 state digest and older record ceilings remain unchanged.

Stable anchor/containment evidence, protected registry, intended-venue
barrier semantics, accounting, grant read-back and the future effect/receipt
writer remain separate gates. Native, provider, tenant, paid, venue and
human acceptance are NOT RUN.
