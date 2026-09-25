# 18d3a source review

Status: independent read-only Standards and Spec re-reviews **PASS**,
2026-09-25. Fixed point: `a6830a8`. The reviewers made no source edits and
claimed no native, tenant, provider or power-loss acceptance.

The first Spec review found that the journal claim view could release facts
if the WAL disappeared between preflight and open. The store now rechecks
WAL presence after taking its lock and before SQLite opens, and the view
requires the opened store's WAL observation before returning facts. A real
SQLite race-injection test removes the WAL between checks and verifies no
facts and no recreated WAL.

Both first reviews requested direct new-view assertions for custody and
anchor corruption rather than relying on old-inspector tests. The tests now
cover journal custody, damaged anchor, forged claim, one-commit lag, WAL
absence, detectable close failure, and the removal race. Ledger view tests
cover a verified empty v1 reservation set, tail lag, persisted hold,
anchor damage, custody failure, failed close, fixture genesis and a crafted
receiver-origin reservation row. The two re-reviews found no remaining
concrete source blocker. Standards also reported Ruff, whitespace checks
and focused tests passing.

The views report stopped-image facts only. The v1 ledger cannot store a
verified reservation; positive durable triples, a production reserve and
any launch permit remain outside this unit. Full-suite validation and exact
artifact hashes are recorded separately.
