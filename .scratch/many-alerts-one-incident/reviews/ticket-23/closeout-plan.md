# Ticket 23 fixed-fixture evidence closeout plan — 2026-09-21

Baseline: local commit `414b689`. Add bounded retained output and verifiable closeout to
fixed local fixtures only. This does not implement production audit storage, a native
adapter, sanitizer, retention policy or launch-to-durable-closeout deadline.

1. Add an evidence module that writes capture/result files exclusively, flushes their
   content, and publishes a versioned digest manifest only after content is complete.
   Keep fixed filenames, bounded reads, exact file sets in the manifest and no overwrite.
2. Integrate after fixed-process cleanup, preserving the existing result and classification.
   Retain merged stdout/stderr bytes in observed read order; do not call this a replayable
   native transcript. Ledger claims remain unresolved until explicit synthetic billing.
3. Add read-back that verifies size/digest and capture/worker/result linkage, rejects
   incomplete/corrupt receipts and keeps native launch CLOSED. Content integrity is not
   independent semantic acceptance, authenticated provenance or same-user tamper defense.
4. Test round-trip, missing/truncated/modified files, unsupported manifest shape, symlink
   and nonregular leaves, publication failure/crash and conservative ledger holds. Run
   the full suite and independent Standards/Spec plus bounded Fable review.

Trusted private output parent and source/interpreter remain requirements. POSIX file and
parent-directory fsync calls provide software-level closeout; no hardware power-loss,
mount/ancestry enforcement, same-user concurrency security or deadline proof is claimed.
