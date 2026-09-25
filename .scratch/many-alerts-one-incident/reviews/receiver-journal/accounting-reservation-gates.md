# 18c reservation gate ledger

Status: source-only gate record, 2026-09-24. Applies the accepted ADR 0013,
ticket 38's proposed accounting contract, and the reviewed 18c-storage design.
This record is not a reservation implementation or an attestation.

## Facts already established locally

- The v1 ledger persists receiver-origin events from `population=unknown` and
  returns read-back event receipts. It rejects fixture genesis and every
  `reservation_created` call. Consistent rollback of database, WAL and anchor
  to an older valid image is locally undetectable.
- The v1 event format has no transition that can authenticate complete opening
  history. It has no provider charge-line, coverage, adjustment, archive,
  continuity-witness or hold-clearing event. Its 8,192-event cap cannot by
  itself guarantee room for an unbounded number of late billing lines.
- The rehearsal journal's v1 exact schema and generation are distinct from
  the experiment-lifetime accounting ledger. No atomic cross-store commit or
  launch handshake exists.

## Evidence required before a production reserve method

| Required input | Evidence/decision needed | Current result |
| --- | --- | --- |
| Opening population | Authoritative source and authenticated snapshot covering all prior experiment attempts, reservations, charges, unresolved exposure and applicable non-model cost from the earliest possible spend. The verifier must establish that absence is meaningful. | Unavailable; remain `unknown`. |
| Provider line identity | Account scope and stable unique charge-line key, multi-request attribution, credit/adjustment relation, currency and timestamp semantics, and collision/conflict behavior. | Unverified. |
| Coverage and lag | Authenticated completeness interval, latest covered provider time, known billing delay and finality rule for each attempt. Partial or stale coverage holds. | Unverified. |
| Liability U | Current candidate/request bounds and provider/client enforcement evidence that supports a defensible upper exposure at reservation; U must be at least the $3 R and count against all applicable limits. | Unverified. |
| Continuity witness | Independent off-ledger checkpoint identity/read-back that detects a mutually consistent rollback or binds a new generation to its predecessor. | No witness selected or provisioned. |
| Retention and repair | Exact archival handoff, duplicate-rejection index and control-event headroom for 52 completed weeks and late lines; preserve unknowns and conflicts without silent eviction. | Design pending; v1 capacity is a hold. |
| Cross-store identity | Journal admission/intent digest, generation, attempt and reservation identities plus crash-safe confirmation/restart join. | Versioned journal and 18d plan pending. |

The external decision is which authoritative billing/opening source and
account scope to trust, how it proves completeness and lag, and which
independent continuity witness is acceptable. A local fixture, a fresh ledger,
a signed operator statement alone, a process exit or a client estimate cannot
answer these questions. No provider call or credential/tenant change is
authorized under the current goal.

## Local work that can proceed

Specify a versioned evidence envelope and verifier rejection taxonomy with
closed fields; distinguish source claims from verified facts. Design archive
and duplicate-index failure semantics and an 18d no-launch bridge. Pure
parsers/reducers and synthetic failure tests may proceed after their own
reviewed plan, but they must be incapable of returning a production reserve
or launch permit from synthetic inputs. Once external evidence is supplied,
review the exact verifier against the actual source semantics before wiring
reservation. Ticket 38 remains open throughout this local work.

The [18g proposed archive format](design-18g-archive-format.md) now details
contiguous event bytes, a derived cumulative duplicate index and ordered
read-back, independent witness, active registration and compaction failure
states. It is not implemented. V1 cannot register an archive; the selected
off-cluster store, witness trust domain and versioned ledger migration remain
open alongside the authoritative billing and opening-history decisions above.
Its index and replay cover one ledger generation only; no compaction or
cross-generation continuity rule is supplied by 18g.
