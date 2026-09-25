# 18d3b source review

Status: independent read-only Standards and Spec re-reviews **PASS**,
2026-09-25. Fixed point: `972332c`. The reviewers made no source edits and
claimed no native, provider, tenant or power-loss acceptance.

The Spec reviewer found that an early accounting-document sentence described
all scanner outcomes as missing or unverified ledger evidence, although a
verified no-intent journal returns `missing_intent`. The wording now scopes
the ledger claim to a verified journal intent. The source maps the journal
claim's `ledger_event_id` to the bridge event ID, rejects changed observable
ledger shape, catches invalid structural facts, maps unexpected comparator
output to a hold, and has no writer or launch caller. Spec recheck passes.

The Standards reviewer found two test-plan gaps: a persisted held ledger
image and an exact assertion of the scanner's closed reason set. Both were
added; a real schema-damaged ledger is opened to persist a hold, then the
scanner returns `ledger_unverified`. Standards recheck passes. The scanner
returns a frozen all-hold result, reads only the two verified views and
does not alter the 18d1 pure comparator.

Focused and full integration tests, static checks, hashes and preserved dirty
read-back are recorded separately. A positive durable reservation and any
dispatch permit remain outside this unit.
