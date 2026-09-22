# Private control listener and permanent shutdown outcome

2026-09-22. PASS for separately authorized local application source and synthetic
socket/filesystem tests. Baseline `2fd58d2` was pushed at the user's explicit
request before this unit. This unit is a local continuation; no additional push
or deployment was performed.

`PrivateControlListener` prepares and publishes a fresh private filesystem Unix
socket under an operator-provisioned parent. Exact mode/UID/GID and inode checks
guard acceptance and conservative cleanup. Noncanonical final path spellings
are rejected, including a confirmed macOS symlink/O_NOFOLLOW bypass through
trailing slash or dot. Cleanup preserves replacements and unknown entries.
Creation rollback and close interrupting a pending accept are covered locally.

`ForwarderControl.shutdown()` permanently holds authority before socket I/O and
interrupts all tracked authenticated or unauthenticated connections. Admission
and command mutation share its shutdown lock. Post-shutdown calls return
`control_closed` even while all four prior slots remain occupied. Held closeout
stays unknown rather than becoming a fabricated successful revocation.

Two Terra workers implemented the listener and its tests; Sol independently
reviewed source and regression coverage. Review findings corrected publication
mode validation, creation rollback, macOS socket-inode assumptions, symlink path
spellings, timeout restoration and lifecycle races. Root implemented controller
shutdown and real pathname authentication/integration tests. The
[review](review.md) records the final source/test hashes and no unresolved findings.

Validation:

- Combined service/lease/control/listener suite: 135 passed in 58.08 seconds.
- Independent final listener/control subset: 55 passed in 3.48 seconds.
- Full repository suite: **1009 passed, 36 skipped in 154.31 seconds**, exit 0.
- Ruff and whitespace checks passed. All four protected dirty files match their
  previously recorded hashes and remain excluded from this unit.

The [validation record](validation.json) binds final artifacts and
[full-suite log](full-suite.txt). Same-UID temporary paths and synthetic secrets
do not establish deployed Receiver/Forwarder/Run separation, Linux peer
credentials, stable ancestors, mount/ACL/group policy or mounted-secret custody.
No native/model/provider request, real credential access, paid experiment, tenant
action, C2 retry or human Report adjudication occurred.

The [next unit](next-supervisor-unit.md) is a reviewed planning input for bounded
accept/worker supervision and observable shutdown completion. Fixed service TLS,
request policies, durable Receiver/accounting and guarded native launch remain
later implementation and acceptance work. No new user input is needed for that
local source/test continuation.
