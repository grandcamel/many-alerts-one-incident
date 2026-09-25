# Unit 18c: exact implementation plan for a non-reserving durable store

Status: proposed for independent review, 2026-09-24. No 18c source edited.
Baseline: `221dab94c8828b101bb1f3a35bbe131e0b1d23bd`.
Decision: [design-18c.md](design-18c.md). This plan covers 18c-storage only.
The separately reviewed trusted-history extension and production reservation
gate are required before any reserve/launch method can exist.

## Ownership and order

1. Add `grafana_jsm_sandbox/accounting_store.py`: private file/SQLite/anchor
   machinery and `LedgerStore` with `create`, `open`, `append`, `inspect`,
   `close`. Add `tests/test_accounting_store.py` with exact schema, custody,
   anchor, replay, duplicate, lock and crash-image cases. The store does not
   import the journal or application entry point.
2. Add `grafana_jsm_sandbox/accounting_ledger.py`: the small Receiver-facing
   wrapper for receiver-only genesis, verified open and sanitized event
   receipts. Add `tests/test_accounting_ledger.py`. Reject fixture genesis and
   every reservation attempt in this phase. No caller may create a trusted
   population, U, provider coverage or launch permit through this wrapper.
3. Add `docs/accounting-ledger.md` describing physical custody, crash windows,
   inspection, limits and non-claims. Update `docs/accounting-transition.md`
   only to link the store and preserve its pure/synthetic wording. Do not edit
   journal DDL, journal goldens, receiver entry points, ticket-19 paths, the
   untracked panel, or old source/tests.

Use a test-first slice for schema/codec and open before append. Verify focused
tests between the storage and wrapper steps. Keep `accounting_events.py` and
`accounting_transition.py` byte-identical unless an independently reviewed
18b defect is reproduced. No 18c change turns `synthetic_complete` into a
trusted state. Stage only the explicit 18c paths.

## Exact physical contract

The directory/file names, modes, SQLite capability/version/settings, DDL,
schema comparison, anchor bytes, slot offsets and fields, custody checks, lock
and no-checkpoint rule are fixed in `design-18c.md`. Encode anchor bodies with
the same canonical ASCII JSON policy as event bodies and a distinct
`acct.anchor.v1\0` SHA-256 domain tag. Enforce a maximum 960-byte anchor body.
Require exact 8192-byte anchor length, exact zero padding outside both slots,
strict field sets/types/UUID/digest syntax, and monotonic two-slot counters.
Never use an anchor digest alone as proof of current billing or external
identity. Event rows bind independent stored digest to canonical bytes;
`replay_accounting` then verifies all semantic and chain rules.

`LedgerStore.create(directory, genesis)` accepts only a receiver v1 genesis
with unknown population, sequence 1, zero prior digest, all distinct IDs and
an absent directory path. It creates and syncs the directory and
database/WAL/anchor under
the lock and reads back genesis and anchor. It leaves every failed create
artifact untouched. `open(directory)` creates no database or anchor and fails
closed on missing/invalid custody or unsupported runtime. `inspect(directory)`
is verify-only, returns code-only status and verified head/identity on success,
and has no append path. A store instance cannot be reused after close or after
an ambiguous write/sync/read-back. `append(event, *, expected_head)` requires
an exact current head digest, checks physical duplicate ID first, rejects
fixture actor and `reservation_created`, applies 18b under the held lock,
checks 8192 cap, commits and anchor-syncs, reads back the row and anchor, and
returns a frozen `EventReceipt`. No receipt means no claimed commit outcome.

After durable-hold and event validation, physical duplicate handling precedes
the head check solely for exact retry:
same event ID and bytes/digest returns a receipt for the original event row
against the currently verified anchor; changed
bytes/digest produces `event_conflict` and latches a hold. A new event ID with
an old expected head returns `stale_head`; a new event with repeated business
identity is rejected by replay. Before any append, compare the in-memory
projection and anchor to a read-back of the current physical head, so a caller
cannot submit a forged projection or move the store beneath the writer.

Open classification is exact: anchor absent/invalid, row/anchor identity or
head conflict, damaged SQLite/row/digest/chain, and replay contradiction are
recovery holds; OS/read errors and newer formats are process holds. An
unanchored, complete one-event tail is adopted after full replay into an
anchor with a durable `tail_adopted_unreconciled` hold in both slots. The held
image remains inspectable but cannot append or reserve until a separately
reviewed reconciliation or continuity-preserving new generation.
Two or more events beyond the anchor refuse. On an append failure, latch the
process store object; after restart, reverify from disk and never re-use the
old receipt. A persistent recovery hold uses the two anchor slots and is
read back before reporting; if an anchor is missing/invalid, leave bytes
untouched and rederive the hold on each open. Do not delete or repair evidence
in place. Produce fixed error codes without paths, raw event content or
exception text.

## Test matrix and acceptance

- Schema: exact `sqlite_schema`/PRAGMAs, wrong application/user version,
  extra table/trigger, malformed columns, read-only/open behavior, and a
  future-format process hold.
- Custody: symlink and hard-link files, mode/owner, path URI chars, missing
  files, short DB/WAL preservation, second process and same-process lock,
  fail-closed unsupported sync/version.
- Anchor: both slots and counter selection, torn/zero/nonzero padding,
  missing/invalid anchor, conflicting identity/head/digest, verified lag one
  adoption, lag two refusal, anchor sync failure, and two-crash hold recovery.
- Transition: receiver unknown genesis cannot reserve; fixture genesis is
  rejected on create and open; seven v1 event kinds' permitted subset replay
  consistently; changed duplicate ID, distinct-ID repeated business key,
  stale head, forged event/projection, malformed body, 8192 cap, no eviction.
- Crash ordering: before SQL commit, SQL committed before anchor, anchor
  synced before read-back, read-back failure, and receipt returned before
  crash. Reopen each image and assert no false receipt or new reservation.
  SIGKILL is local process evidence only. A test explicitly demonstrates
  undetectable consistent rollback and marks external witness unresolved.
- Sanitation: no credential, raw prompt, source payload, Ground truth or
  provider line in store/receipt/errors. No application caller imports the
  new wrapper; existing journal and opt-in front door remain admission-only.

Run focused tests with the loopback guard, Ruff on new Python, line-length and
whitespace checks, and `git diff --check`. After all code changes, run the
full test suite with `DEMO_END_TO_END` and `DEMO_CONTAINER` unset before a
local commit; fix failures. Preserve/read back protected dirty hashes and
review all source/test/docs against this exact plan. Record test counts,
artifact hashes, failure injections, reviewer verdict and NOT RUN boundaries.
No push/publication, C2 retry, provider/model call, deployment or paid Run.

## Gates before the next plan

Do not code 18c-reservation or 18d from this plan. Their reviewed plan must
first fix the provider/opening manifest shape and authoritative verifier,
versioned attestation transition, archive and duplicate index with 52-week
retention, unbounded repair headroom or a proved finite line bound, external
rollback witness, and journal intent/confirmation migration. A failed gate
leaves the durable store inspectable and the model dispatch hold in force.
