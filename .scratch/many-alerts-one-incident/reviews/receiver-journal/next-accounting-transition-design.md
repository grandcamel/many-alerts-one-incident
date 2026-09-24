# Accounting transition and durability design after 18a

Status: selected local design, 2026-09-24. Reconciled against `11834600c712cf3f9851a989ed4c8e82fd4d806c`.
This is a proposed implementation path under the existing local source/test authority,
not an amendment to ADR 0013 or permission for paid/native/provider work.

## Alternatives and judgment

| Design | Benefit | Obligation and ruling |
| --- | --- | --- |
| New tables in the present journal database | Reservation and journal evidence could commit together | Its exact v1 SQLite schema rejects added tables. A versioned migration, anchor/replay extension and experiment lifetime across journal resets need a separate, large design. Defer. |
| New accounting event types in the existing journal table | Reuses the anchored commit chain without a SQL migration | The journal is rehearsal scoped and capped at 10,000 admissions; 52-week accounting, reset continuity and billing repair headroom remain unresolved. Defer. |
| Separate Receiver-owned accounting ledger with a journal handshake | Independent experiment identity, retention and capacity horizon; preserves the v1 journal store | Adds cross-store crash states and recovery joins. Select, conditional on the mandatory no-launch handshake below. |
| Pure transition/replay before physical storage | Proves history and state rules at a small seam | Select as 18b. Its output has no durability or dispatch authority. |

The current schema makes an unversioned table addition incompatible; it does not
prove a separate ledger is inherently necessary. This is an engineering choice
for bounded implementation and distinct retention. Reconsider it if the bridge
cannot meet the crash and recovery obligations. No nullable/fake reservation
profile is allowed for Run lifecycle.

## Selected sequence

**18b, pure transition/replay.** Define a closed version-1 accounting event
format and deterministic projection. Genesis starts with an unknown population;
the only complete-population fixture is explicitly synthetic. Registration and
reservation transitions rebuild facts from the current event head and call the
18a policy anew at a supplied UTC instant. Exact replay is idempotent; changed
identity, gap, fork, invalid linkage, stale head or incomplete history refuses.
All committed reservations conservatively count once and retain U. An event or
proposal cannot be a receipt, launch permit or authenticated coverage claim.

**18c, durable ledger.** A separate exclusive-writer store will persist the
closed events with an exact physical schema, append-only checks, sync and
verified anchor; open must replay and compare its head. A reservation service
must re-evaluate under that writer lock and return a read-back committed
receipt. A missing/corrupt/ambiguous ledger, stale snapshot or capacity
failure holds. The 18b closed v1 subset cannot attain trusted complete
population: 18c therefore needs a separately reviewed compatible format
extension and external opening-history/coverage verifier before any production
reservation. Creation cannot certify prior billing history. Archive,
duplicate-rejection index, retained summaries and control/repair capacity need
their own exact plan before implementation; four future-event slots cannot
cover arbitrary billing lines, adjustments and holds.

**18d, journal bridge, admission-only.** Commit a journal reservation intent
against an already admitted Notification; reserve idempotently in the ledger;
read back its receipt; commit a matching journal confirmation. An ambiguous
intent commit stops before calling the ledger. Missing confirmation is unknown,
not zero cost; a ledger reservation without confirmation retains U. A
confirmation lacking its reservation, a mismatched identity/head, or either
store unavailable holds. Restart scans both verified stores before considering
any future launch. The later lifecycle still needs a current hold/identity
recheck, lease, durable launch claim, containment and staleness policy. It
cannot use an old immutable receipt alone. These are binding requirements for
the 18c/18d plans, not features delivered by 18b.

## Identity, history and recovery contracts

The ledger owns a stable experiment UUID plus ledger UUID and generation.
Each journal origin is its full journal UUID and generation, linked to that
experiment; every reservation retains admission and intent references,
attempt/reservation/Run/lease IDs, original week, profile, lineage, R/U,
evidence references and policy revision. A new journal generation or root
cannot reset the experiment budget. An unbound journal or restored store is a
hold. A full restoration of both stores to a self-consistent older image
cannot be detected without an external witness; local tests make no such claim.

The existing 18a `Snapshot` has one current journal generation while past
attempts can originate in other generations. Its `Attempt` has no origin
field, so the transition projection must preserve/check those origins before
building the 18a view. The 18a 512-attempt bound counts *all* history, not
only unsettled attempts. Until verified summaries/archive are implemented,
the initial subset must refuse at this lifetime bound. No truncation, reset,
synthetic zero or aggregate shortcut makes the population complete.

Unknown, stale or conflicted U, provider coverage or earlier population
blocks new reservation. The 18b complete-population marker is a synthetic
test assumption. A durable adapter must independently authenticate opening
history, configuration, U and current journal head. Estimates, process exits,
partial provider lines and rollover never release U. No provider-line import,
settlement, refunds, hold clearing or archive occurs in 18b.

## Independent critique and reconciliation

Two independent designs considered a versioned one-store journal and a
separate ledger. The independent critic accepted pure replay only if it
reconstructs state, rejects incomplete/ambiguous history, and re-evaluates at
the current head. This decision incorporates its identity, provenance,
512-row, future-capacity and bridge requirements. The critic's suggested
duplicate charge-line test belongs to the later provider import unit, since
18b has no charge-line event. Tests and implementation are NOT RUN for this
design record. The next artifact is the exact 18b implementation plan and
its reconciliation before source changes.
