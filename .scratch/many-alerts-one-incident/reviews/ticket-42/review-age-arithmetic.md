# Ticket 42a venue age arithmetic source review

Status: independent Standards and Spec reviews PASS, 2026-09-25.
Baseline: `25dd475`. Reviewed source and tests: `venue_age.py` and
`test_venue_age.py`.

Both reviews found the first same-boot and new-boot fixtures too weak: their
fresh lower bounds dominated the prior lower bounds, so removing prior-lower
carry would still pass. The fixtures now make the advanced/carried prior lower
dominate and assert exact lower and upper outputs. Both reviewers read back
the correction and confirmed PASS. Focused tests and Ruff pass.

The review covers claimed-time arithmetic and validation only. It does not
authenticate provider creation/now, prove timestamp placement within the
request, establish a durable off-cluster anchor, or authorize admission,
creation, teardown or a Run.
