# 18d3a design and plan review

Status: **ACCEPT_LOCAL_18D3A_READ_ONLY_PLAN**, 2026-09-25. Fixed point:
`92aace8`. Independent Standards and Spec reviewers read the design and
file-by-file plan against the current journal and ledger inspectors, the 18d
bridge and the accepted accounting boundary. They made no edits and ran no
tests.

Both reviewers found the first draft's positive durable fixture path
impossible: the v1 ledger store rejects fixture genesis and every reservation
event on create and replay. The revised ledger view can return only a verified
Receiver/`unknown` head with an empty reservation tuple. Crafted fixture and
reservation images must be rejected. Positive durable triples require a
separate reviewed store format; pure synthetic triples retain their label.

The journal view now requires zero anchor lag before releasing claim facts.
It translates detectable `os.close` failures into unverified no-facts results
without changing the old inspection report. Suppressed lower-level close or
unlock errors cannot be claimed as detected. Custody and corruption retain
each existing inspector's fixed-code `held`/`unverified` classification.
The reviewers re-read these corrections and found no remaining plan blocker.

This is a documentation-only checkpoint. Focused and full tests are **NOT
RUN** for this commit. Source review must verify no-write custody, exact
old-report compatibility and the empty v1 ledger result. Production reserve,
cross-store permit, native/provider/tenant/venue/paid execution, power-loss
durability and human adjudication remain **NOT RUN**.
