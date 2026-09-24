# Unit 18b outcome

Status: local pure/synthetic accounting transition, 2026-09-24.
Baseline: `11834600c712cf3f9851a989ed4c8e82fd4d806c`.

New `accounting_events.py` and `accounting_transition.py` implement a closed
canonical event format and deterministic replay of synthetic accounting
history. The projection retains experiment and journal origins, original
week, full attempted-Run identities and U liability. A reservation event is
re-evaluated through 18a at the current projected head. Missing population,
configuration, bindings, stale U, conflicting identity, chain gaps and sticky
holds refuse. Public apply rebuilds its projection from event bytes so a
caller cannot remove earlier liability by replacing a dataclass field.

No existing source, tests, journal SQL, goldens, entry points or protected
dirty paths changed. New tests and [documentation](../../../../docs/accounting-transition.md)
state the synthetic provenance and no-launch limits. The [design decision](next-accounting-transition-design.md),
[exact plan](implementation-plan-18b.md), [independent review](review-18b.md)
and [validation record](validation-18b.json) hold the local evidence.

The 18b event set has no trusted history-attestation transition. It cannot
produce a production reservation, durable receipt or launch authority. The
next source step is a separately planned durable ledger with verified opening
history/coverage and bounded repair capacity, followed by a journal intent,
idempotent reserve, confirmation and recovery-scan bridge. The existing 18a
512 lifetime-row bound and strict $50 cap remain conservative; archival
summaries, provider settlement, credits/refunds, holds clearing and concurrent
writer handling are still absent.

Final test counts and hashes are in `validation-18b.json`. Provider, native,
tenant, venue, paid, deployment, power-loss durability, dispatch and human
Report adjudication were NOT RUN. Ticket 38 and Run lifecycle remain open.
No push/publication or C2 retry occurred.
