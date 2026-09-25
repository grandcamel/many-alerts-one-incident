# 19k local permit-fence contract outcome

Date: 2026-09-25. Fixed point: `43b5a03`.

The proposed [19k design](design-19k-dispatch-permit-seam.md) reconciles the
ticket-36 Forwarder specification with reviewed 19h: a future Receiver
effect-intent authorization precedes L1, a one-use permit is consumed at L1,
and L2 rechecks the consumed binding immediately before the first possible
upstream byte. Pre-L1 NOT_DISPATCHED and post-L1 FAILED require trusted,
finalized receipts and their respective no-connect/zero-byte evidence;
deadline sweep or receipt failure holds unknown. The existing control session
cannot carry reverse requests, so a future authorization exchange requires
its own authenticated, bounded Receiver endpoint. A fresh post-append journal
and ledger qualification is required before any permit reply.

Independent Standards and Spec document reviews found and then cleared the
reverse-control/frame-capacity mismatch, missing post-append qualification,
overstated receipt finalization, and separate endpoint capacity claim. Both
reviewers report PASS on the revised contract. `git diff --check` passes.
This is documentation only; tests, native/provider/tenant work, and positive
permit behavior are **NOT RUN**. Current permit routes remain denied. The
Receiver accounting population, effect writer, service-grant mapping,
logical-operation adapter, intended venue and external read-back gates remain
open under tickets 36–38.
