# 19j1: unqualified Run-intent record and replay

Status: local implementation plan, 2026-09-25. Fixed point: `9ea0a4b`.
Authority: reviewed 19j design, ADRs 0011–0013, tickets 36–38.
No application writer, ledger-positive path, grant registration, process or
permit is in scope.

## Concrete record choice

Use `(run_intent, 3)` with actor `receiver`. Its event ID is a fresh canonical
UUID, distinct from the v3 reservation claim and its confirmation. The `ids`
object binds the existing v3 job, admission, intent, attempt, reservation,
Run and model lease IDs. The `data` object binds the exact replay-available
initial claim and confirmation, the *claimed* ledger event, a syntactically
valid caller-supplied ledger head reference
`{"sequence": 1..MAX_SEQ, "event_digest": hex64}`, current original-admission
member count/digest, fixed 270/290/300-second policy milestones, and a sorted
service-claim array. It requires all four current mandatory profiles and
permits scoped Confluence only as a fifth. Every service has one distinct
canonical journal UUID lease claim and a hex64 scope digest; `anthropic`
uses the v3 accounting `lease_id`. All service lease claims are distinct from
one another and from the journal, admission, job, intent, attempt,
reservation, Run, confirmation-event, claimed ledger UUID, claimed ledger
event ID and Run-intent event UUIDs.
The data also stores `based_on_commit_seq` and `based_on_record_digest` from
the exact current journal head, both re-derived at replay. The ledger head
sequence must be at least the claimed event sequence; an equal sequence
must have the same event digest. These are structural checks, not ledger
authentication. A separate `rj.run-intent.v3` digest covers
all content fields except itself. Every exposed projection/inspection label
is `outstanding_unqualified`.

Five-service representative canonical content measures about 2.5 KiB, above
the existing 2,048-byte cap shared by v2/v3 reservation and hold records.
Set a **4,096-byte cap only for `(run_intent, 3)`**; preserve the 2,048-byte
limit for every existing private type. Before freezing the validator, measure
the worst-case bounded five-service record with maximum legal counters,
boot ID and field lengths, not just a representative sample; reduce fields
or revise this proposed cap if that shape does not fit. The record is
ordinary-class and its full charge must fit `ordinary_bytes`, so it cannot
consume the configured recovery reserve. A separate one-slot v3 Run-intent
projection and digest keep the original `rj.state.v1` formula and all older
projection digests unchanged. The slot stays outstanding until a separately
reviewed disposition record exists.

## File-by-file sequence

1. `journal_records.py`: add the private version/actor/class map, exact
   validator and type-specific size limit. Keep v1 registry, v2/v3 existing
   validators and bytes unchanged. Focused codec checks before moving on.
2. `journal_reducer.py`: add one `RunIntentClaim` projection slot and delta,
   pure `plan_run_intent`, replay re-derivation and a separately tagged
   projection digest. Require current v3 claim and confirmation, no global
   dispatch or job hold, exact current original-admission members, all
   mandatory services, distinct lease claims and ordinary capacity. A
   caller-supplied ledger head is syntax only; the planner never returns a
   positive reservation or permit. Verify pure and mixed-version tests.
3. `recovery_journal.py`: add count/digest/outstanding-unqualified summary to
   live snapshot and stopped verify-only report, with no writer or positive
   claim view. Verify real SQLite/WAL reopen and older-binary process hold.
4. Independent Standards/Spec source reviews; fix findings; changed-file
   Ruff, targeted tests, full suite; record truthful outcome/ticket updates;
   read back protected dirty work; stage only named files and commit locally.

The current Receiver ledger has `population=unknown` and no reservation
events. No source fixture from this unit qualifies provider spend, current
ledger match, venue durability, native transport or human adjudication.
